# Historial de Conversación 1 - AlpacaNode Proyecto Trading

## Resumen Inicial
El usuario inició el proyecto para crear un bot de trading algorítmico 24/7 usando Alpaca y Python, enfocado inicialmente en ETFs y Cripto.

## Hitos Alcanzados
1.  **Motor de ETFs**: Implementación de estrategias como EMA Cross y RSI Mean Reversion sobre QQQ, SPY, etc.
2.  **Motor de Cripto**: Implementación de 10 estrategias avanzadas (EMA Ribbon, VWAP, Arbitrage, Sentiment, etc.) usando el feed de Alpaca Crypto.
3.  **Equities Engine**: Creación de un tercer motor para acciones individuales de alta volatilidad con:
    *   **PreMarketScreener**: Escaneo diario de gappers.
    *   **RegimeManager**: Filtrado por modo de mercado (BULL/BEAR/CHOP).
    *   **10 Estrategias**: Gapper Momentum, VCP, Gamma Squeeze, NLP Sentiment (FinBERT), etc.
4.  **Dashboard Unificado**: Interfaz HTML con 3 pestañas para monitoreo en tiempo real.
5.  **Fix de Arquitectura**: Refactorización para compartir el stream IEX de Alpaca entre el motor de ETF y el de Equities, evitando el límite de conexión única para stocks.

## Problemas en Resolución
*   **Límite de Conexión de Alpaca**: Error 429/406 recurrente. Se sospecha conflicto entre el stream de Stocks y el de Cripto bajo el mismo API Key en el Tier Gratuito.
*   **Mejoras en Dashboard**: Discrepancias en P&L (hardcoded initial capital), falta de historial gráfico (D/W/M) y gráficos por símbolo.

## Decisiones Técnicas
*   **NLP**: Uso de `finbert-tone` en CPU-only para optimizar los 4GB de RAM del VPS.
*   **Docker**: Optimización de la instalación de `torch` para evitar fallos de build y excesivo consumo de recursos.
