// TradingViewWidget.jsx
import React, { memo, useEffect, useRef } from 'react';

function TradingViewWidget() {
  const container = useRef();
  const scriptLoaded = useRef(false);

  useEffect(
    () => {
      // Prevenir múltiples cargas del mismo script
      if (scriptLoaded.current) {
        return;
      }

      // Limpiar cualquier contenido previo
      if (container.current) {
        container.current.innerHTML = '';
      }

      const script = document.createElement("script");
      script.src = "https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js";
      script.type = "text/javascript";
      script.async = true;
      script.innerHTML = `
        {
          "lineWidth": 2,
          "lineType": 0,
          "chartType": "candlesticks",
          "fontColor": "rgb(106, 109, 120)",
          "gridLineColor": "rgba(242, 242, 242, 0.06)",
          "volumeUpColor": "rgba(34, 171, 148, 0.5)",
          "volumeDownColor": "rgba(247, 82, 95, 0.5)",
          "backgroundColor": "#0F0F0F",
          "widgetFontColor": "#DBDBDB",
          "upColor": "#22ab94",
          "downColor": "#f7525f",
          "borderUpColor": "#22ab94",
          "borderDownColor": "#f7525f",
          "wickUpColor": "#22ab94",
          "wickDownColor": "#f7525f",
          "colorTheme": "dark",
          "isTransparent": false,
          "locale": "en",
          "chartOnly": false,
          "scalePosition": "right",
          "scaleMode": "Normal",
          "fontFamily": "-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif",
          "valuesTracking": "1",
          "changeMode": "price-and-percent",
          "symbols": [
            [
              "BINANCE:BTCUSDT|1D"
            ],
            [
              "BINANCE:ETHUSDT|1D"
            ],
            [
              "BINANCE:BNBUSDT|1D"
            ],
            [
              "BINANCE:SOLUSDT|1D"
            ],
            [
              "BINANCE:XRPUSDT|1D"
            ],
            [
              "BINANCE:DOGEUSDT|1D"
            ],
            [
              "BINANCE:ADAUSDT|1D"
            ]
          ],
          "dateRanges": [
            "1d|1",
            "1m|30",
            "3m|60",
            "12m|1D",
            "60m|1W",
            "all|1M"
          ],
          "fontSize": "10",
          "headerFontSize": "medium",
          "autosize": true,
          "width": "100%",
          "height": "100%",
          "noTimeScale": false,
          "hideDateRanges": false,
          "hideMarketStatus": false,
          "hideSymbolLogo": false
        }`;
      
      if (container.current) {
        container.current.appendChild(script);
        scriptLoaded.current = true;
      }

      // Cleanup function
      return () => {
        scriptLoaded.current = false;
      };
    },
    []
  );

  return (
    <div className="tradingview-widget-container" ref={container}>
      <div className="tradingview-widget-container__widget"></div>
      <div className="tradingview-widget-copyright"><a href="https://www.tradingview.com/markets/" rel="noopener nofollow" target="_blank"><span className="blue-text">World markets</span></a> by TradingView</div>
    </div>
  );
}

export default memo(TradingViewWidget);
