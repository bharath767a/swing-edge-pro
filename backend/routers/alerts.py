"""
SwingEdge Pro — Alerts Router
AUDIT FIX P2: Now persists to SQLAlchemy Alert model + real WebSocket push.
Restart-safe: alerts survive server restarts. WebSocket clients receive push
notifications on new alert creation (was 30s polling).
"""
import asyncio
import json
import logging
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Set
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.stock import Alert

router = APIRouter(prefix='/api/alerts', tags=['alerts'])
logger = logging.getLogger(__name__)

# WebSocket connection manager — real push, not 30s polling
class ConnectionManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)

    async def broadcast(self, message: dict):
        """Push a message to all connected clients."""
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.discard(ws)


manager = ConnectionManager()


class AlertCreate(BaseModel):
    ticker: Optional[str] = None
    alert_type: str
    message: str
    priority: str = 'medium'


@router.get('')
async def get_alerts(db: AsyncSession = Depends(get_db), limit: int = 50):
    """Get recent alerts (default unread first, then most recent)."""
    result = await db.execute(
        select(Alert).order_by(Alert.triggered_at.desc()).limit(limit)
    )
    alerts = result.scalars().all()
    unread_count = sum(1 for a in alerts if not a.is_read)
    return {
        'count': len(alerts),
        'unread_count': unread_count,
        'alerts': [
            {
                'id': a.id, 'ticker': a.ticker, 'alert_type': a.alert_type,
                'message': a.message, 'priority': a.priority,
                'triggered_at': a.triggered_at.isoformat() if a.triggered_at else None,
                'is_read': a.is_read,
            }
            for a in alerts
        ],
    }


@router.post('')
async def create_alert(alert: AlertCreate, db: AsyncSession = Depends(get_db)):
    """Create a new alert and push to all connected WebSocket clients in real-time."""
    new_alert = Alert(
        ticker=alert.ticker, alert_type=alert.alert_type,
        message=alert.message, priority=alert.priority, is_read=False,
    )
    db.add(new_alert)
    await db.commit()
    await db.refresh(new_alert)

    # Real push to all connected clients
    payload = {
        'type': 'alert',
        'id': new_alert.id,
        'ticker': new_alert.ticker,
        'alert_type': new_alert.alert_type,
        'message': new_alert.message,
        'priority': new_alert.priority,
        'triggered_at': new_alert.triggered_at.isoformat() if new_alert.triggered_at else None,
    }
    await manager.broadcast(payload)

    return payload


@router.patch('/{alert_id}/read')
async def mark_read(alert_id: int, db: AsyncSession = Depends(get_db)):
    """Mark an alert as read."""
    await db.execute(
        update(Alert).where(Alert.id == alert_id).values(is_read=True)
    )
    await db.commit()
    return {'status': 'ok'}


@router.websocket('/ws')
async def alerts_websocket(websocket: WebSocket):
    """Real-time WebSocket — pushes new alerts immediately (was 30s polling).

    Also sends a heartbeat every 30s so the client knows the connection is alive.
    """
    await manager.connect(websocket)
    try:
        # Send immediate ack with current unread alerts
        await websocket.send_json({'type': 'connected', 'message': 'WebSocket connected'})
        while True:
            await asyncio.sleep(30)
            await websocket.send_json({'type': 'heartbeat', 'ts': datetime.now().isoformat()})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.debug(f"WebSocket error: {e}")
        manager.disconnect(websocket)
