from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from models.models import Product
from models.schemas import ProductCreate, ProductUpdate, ProductResponse
from src.dependencies import get_db

router = APIRouter(prefix="/api/products", tags=["products"])


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(product: ProductCreate, db: AsyncSession = Depends(get_db)):
    """Create a new product"""
    try:
        new_product = Product(
            name=product.name,
            description=product.description,
            price=product.price,
            stock=product.stock,
        )
        db.add(new_product)
        await db.commit()
        await db.refresh(new_product)
        return new_product
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create product: {str(e)}",
        )


@router.get("", response_model=list[ProductResponse])
async def get_all_products(db: AsyncSession = Depends(get_db)):
    """Get all products (including inactive ones)"""
    try:
        result = await db.execute(select(Product))
        products = result.scalars().all()
        return products
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch products: {str(e)}",
        )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    """Get a product by ID (including inactive ones)"""
    try:
        result = await db.execute(select(Product).where(Product.id == product_id))
        product = result.scalars().first()

        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )
        return product
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch product: {str(e)}",
        )


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int, product_update: ProductUpdate, db: AsyncSession = Depends(get_db)
):
    """Update a product"""
    try:
        result = await db.execute(select(Product).where(Product.id == product_id))
        product = result.scalars().first()

        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )

        # Update fields if provided
        if product_update.name is not None:
            product.name = product_update.name
        if product_update.description is not None:
            product.description = product_update.description
        if product_update.price is not None:
            product.price = product_update.price
        if product_update.stock is not None:
            product.stock = product_update.stock

        db.add(product)
        await db.commit()
        await db.refresh(product)
        return product
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update product: {str(e)}",
        )


@router.patch("/{product_id}/deactivate", response_model=ProductResponse)
async def deactivate_product(product_id: int, db: AsyncSession = Depends(get_db)):
    """Deactivate a product (soft delete - only set is_active to false)"""
    try:
        result = await db.execute(select(Product).where(Product.id == product_id))
        product = result.scalars().first()

        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )

        product.is_active = False
        db.add(product)
        await db.commit()
        await db.refresh(product)
        return product
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to deactivate product: {str(e)}",
        )


@router.patch("/{product_id}/activate", response_model=ProductResponse)
async def activate_product(product_id: int, db: AsyncSession = Depends(get_db)):
    """Activate a product"""
    try:
        result = await db.execute(select(Product).where(Product.id == product_id))
        product = result.scalars().first()

        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )

        product.is_active = True
        db.add(product)
        await db.commit()
        await db.refresh(product)
        return product
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to activate product: {str(e)}",
        )
