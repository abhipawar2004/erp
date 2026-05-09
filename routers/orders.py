from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, joinedload
from decimal import Decimal

from models.models import Order, OrderItem, Product, OrderStatus
from models.schemas import OrderCreate, OrderResponse, OrderStatusUpdate, OrderItemCreate
from src.dependencies import get_db

router = APIRouter(prefix="/api/orders", tags=["orders"])


async def adjust_stock(order, db, restore=False):
    """Adjust product stock for an order based on the requested transition."""
    for order_item in order.order_items:
        result = await db.execute(
            select(Product).where(Product.id == order_item.product_id)
        )
        product = result.scalars().first()

        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with ID {order_item.product_id} not found",
            )

        if restore:
            # Restoring stock is used when an order moves into CANCELLED.
            product.stock += order_item.quantity
        else:
            # Re-reserving stock is used when an order leaves CANCELLED.
            if product.stock < order_item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Insufficient stock for product {product.name}. "
                        f"Available: {product.stock}, Requested: {order_item.quantity}"
                    ),
                )
            product.stock -= order_item.quantity

        db.add(product)

    
@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(order: OrderCreate, db: AsyncSession = Depends(get_db)):
    """Create a new order with inventory stock validation and reduction"""
    try:
        # Validate that order has at least one item
        if not order.order_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order must contain at least one item",
            )

        # Step 1: Validate all products and check stock availability
        product_map = {}
        total_amount = Decimal("0.00")

        for item in order.order_items:
            # Validate quantity
            if item.quantity <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Quantity must be greater than 0",
                )

            # Fetch product
            result = await db.execute(
                select(Product).where(Product.id == item.product_id)
            )
            product = result.scalars().first()

            if not product:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Product with ID {item.product_id} not found",
                )

            # Validate product is active
            if not product.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Product {product.name} is inactive and cannot be ordered",
                )

            # Validate stock availability
            if product.stock == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Product {product.name} is out of stock",
                )

            if product.stock < item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient stock for product {product.name}. Available: {product.stock}, Requested: {item.quantity}",
                )

            product_map[item.product_id] = {
                "product": product,
                "quantity": item.quantity,
            }
            total_amount += Decimal(str(product.price)) * Decimal(str(item.quantity))

        # Step 2: Create order
        new_order = Order(
            status=OrderStatus.PENDING,
            total_amount=total_amount,
        )
        db.add(new_order)
        await db.flush()  # Flush to get the order ID without committing

        # Step 3: Reduce stock and create order items
        for item in order.order_items:
            product_info = product_map[item.product_id]
            product = product_info["product"]
            quantity = product_info["quantity"]

            # Reduce product stock
            product.stock -= quantity
            db.add(product)

            # Create order item
            order_item = OrderItem(
                order_id=new_order.id,
                product_id=item.product_id,
                quantity=quantity,
                price=product.price,
            )
            db.add(order_item)

        # Step 4: Commit transaction
        await db.commit()
        await db.refresh(new_order)

        # Load order items for response
        result = await db.execute(
            select(Order)
            .where(Order.id == new_order.id)
            .options(selectinload(Order.order_items).joinedload(OrderItem.product))
        )
        created_order = result.scalars().first()

        return created_order

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create order: {str(e)}",
        )


@router.get("", response_model=list[OrderResponse])
async def get_all_orders(db: AsyncSession = Depends(get_db)):
    """Get all orders"""
    try:
        result = await db.execute(
            select(Order).options(selectinload(Order.order_items).joinedload(OrderItem.product))
        )
        orders = result.unique().scalars().all()
        return orders
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch orders: {str(e)}",
        )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    """Get order by ID"""
    try:
        result = await db.execute(
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.order_items).joinedload(OrderItem.product))
        )
        order = result.scalars().first()

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )
        return order
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch order: {str(e)}",
        )


@router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: int, status_update: OrderStatusUpdate, db: AsyncSession = Depends(get_db)
):
    """Update order status"""
    try:
        requested_status = status_update.status.strip().upper()
        valid_statuses = [status.value for status in OrderStatus]

        # Validate the requested status before applying any inventory changes.
        if requested_status not in OrderStatus.__members__:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Allowed values: {', '.join(valid_statuses)}",
            )

        # Fetch order
        result = await db.execute(
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.order_items))
        )
        order = result.scalars().first()

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        current_status = order.status.value
        if current_status == requested_status:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order is already in the requested status",
            )

        # Transition-based inventory management:
        # - moving into CANCELLED restores stock once
        # - moving out of CANCELLED reserves stock again
        # - transitions between active statuses do not change stock
        if current_status != OrderStatus.CANCELLED.value and requested_status == OrderStatus.CANCELLED.value:
            await adjust_stock(order, db, restore=True)
        elif current_status == OrderStatus.CANCELLED.value and requested_status != OrderStatus.CANCELLED.value:
            await adjust_stock(order, db, restore=False)

        # Update status
        order.status = OrderStatus[requested_status]
        db.add(order)
        await db.commit()
        await db.refresh(order)

        # Reload with relationships
        result = await db.execute(
            select(Order)
            .where(Order.id == order.id)
            .options(selectinload(Order.order_items).joinedload(OrderItem.product))
        )
        updated_order = result.scalars().first()

        return updated_order
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update order status: {str(e)}",
        )


@router.patch("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(order_id: int, db: AsyncSession = Depends(get_db)):
    """Cancel an order using the shared status transition handler."""
    try:
        return await update_order_status(
            order_id,
            OrderStatusUpdate(status=OrderStatus.CANCELLED.value),
            db,
        )
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to cancel order: {str(e)}",
        )
