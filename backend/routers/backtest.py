from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from backend.engine.backtester import Backtester, STRATEGIES
import logging

router = APIRouter(prefix='/api/backtest', tags=['backtest'])
logger = logging.getLogger(__name__)
_backtester = Backtester()

class BacktestRequest(BaseModel):
    strategy: str
    ticker: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    initial_capital: float = 10000.0

@router.get('/strategies')
async def get_strategies():
    return {'strategies': [{'id': k, 'name': v} for k, v in STRATEGIES.items()]}

@router.post('/run')
async def run_backtest(req: BacktestRequest):
    try:
        results = _backtester.run_backtest(
            strategy=req.strategy,
            ticker=req.ticker,
            start_date=req.start_date,
            end_date=req.end_date,
            initial_capital=req.initial_capital,
        )
        return {
            'strategy': results.strategy, 'ticker': results.ticker,
            'win_rate': results.win_rate, 'avg_gain': results.avg_gain,
            'avg_loss': results.avg_loss, 'sharpe': results.sharpe,
            'max_drawdown': results.max_drawdown, 'total_trades': results.total_trades,
            'profit_factor': results.profit_factor, 'total_return': results.total_return,
            'equity_curve': results.equity_curve or [],
            'trades': (results.trades or [])[:50],
        }
    except Exception as e:
        return {'error': str(e), 'strategy': req.strategy, 'total_trades': 0}
