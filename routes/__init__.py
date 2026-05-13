# routes/__init__.py
from .produits import produits_bp
from .ventes import ventes_bp
from .stocks import stocks_bp
from .appro import appro_bp
from .ml import ml_bp
from .dashboard import dashboard_bp
from .rapports import rapports_bp

__all__ = [
    'produits_bp',
    'ventes_bp', 
    'stocks_bp',
    'appro_bp',
    'ml_bp',
    'dashboard_bp',
    'rapports_bp'
]