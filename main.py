from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import products, orders

app = FastAPI(
    title="Inventory Management System",
    description="FastAPI backend for ERP Inventory Management",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(products.router)
app.include_router(orders.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Inventory Management System API"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}
