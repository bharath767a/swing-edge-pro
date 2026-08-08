"""
SwingEdge Pro — Watchlist Router
AUDIT FIX P2: Now persists to SQLAlchemy WatchlistItem model (was in-memory _watchlist = []).
Restart-safe: user data survives server restarts.
"""
import asyncio
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.stock import WatchlistItem

router = APIRouter(prefix='/api/watchlist', tags=['watchlist'])
logger = logging.getLogger(__name__)


class WatchlistAdd(BaseModel):
    ticker: str
    notes: Optional[str] = ''
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    entry_price: Optional[float] = None


@router.get('')
async def get_watchlist(db: AsyncSession = Depends(get_db)):
    """Get all watchlist items — persisted across restarts."""
    result = await db.execute(select(WatchlistItem).order_by(WatchlistItem.added_at.desc()))
    items = result.scalars().all()
    return {
        'count': len(items),
        'items': [
            {
                'ticker': w.ticker,
                'notes': w.notes,
                'target_price': w.target_price,
                'stop_loss': w.stop_loss,
                'entry_price': w.entry_price,
                'added_at': w.added_at.isoformat() if w.added_at else None,
            }
            for w in items
        ],
    }


@router.post('')
async def add_to_watchlist(item: WatchlistAdd, db: AsyncSession = Depends(get_db)):
    """Add a ticker to the watchlist (idempotent — re-adding updates existing)."""
    ticker = item.ticker.upper()
    # Check if exists
    result = await db.execute(select(WatchlistItem).where(WatchlistItem.ticker == ticker))
    existing = result.scalar_one_or_none()
    if existing:
        # Update fields
        existing.notes = item.notes
        existing.target_price = item.target_price
        existing.stop_loss = item.stop_loss
        existing.entry_price = item.entry_price
        await db.commit()
        return {
            'ticker': existing.ticker, 'notes': existing.notes,
            'target_price': existing.target_price, 'stop_loss': existing.stop_loss,
            'entry_price': existing.entry_price, 'updated': True,
        }
    new_item = WatchlistItem(
        ticker=ticker, notes=item.notes, target_price=item.target_price,
        stop_loss=item.stop_loss, entry_price=item.entry_price,
    )
    db.add(new_item)
    await db.commit()
    return {
        'ticker': new_item.ticker, 'notes': new_item.notes,
        'target_price': new_item.target_price, 'stop_loss': new_item.stop_loss,
        'entry_price': new_item.entry_price, 'added_at': new_item.added_at.isoformat() if new_item.added_at else None,
    }


@router.delete('/{ticker}')
async def remove_from_watchlist(ticker: str, db: AsyncSession = Depends(get_db)):
    """Remove a ticker from the watchlist."""
    ticker = ticker.upper()
    await db.execute(delete(WatchlistItem).where(WatchlistItem.ticker == ticker))
    await db.commit()
    return {'status': 'removed', 'ticker': ticker}
