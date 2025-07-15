### Data Fetched

The bot fetches two main types of data from the CoinSwitch API:

1.  **Ticker Data:** It retrieves real-time ticker information for all available **spot** and **futures** trading pairs. This includes the best bid and ask prices for each pair.
2.  **Funding Rates:** For each futures contract, the bot fetches the current funding rate. The funding rate is a periodic payment made to or by traders holding open positions in futures markets.

### Extracted Information

From the fetched data, the bot extracts the following key pieces of information for each trading pair:

*   **Spot Price:** The current market price to buy the asset on the spot market.
*   **Futures Price:** The current market price to sell the asset on the futures market.
*   **Funding Rate:** The rate of the next funding payment. A positive funding rate means that traders who are short (selling) the futures contract will receive a payment from traders who are long (buying).

### Trading Decision Logic

The `logic_engine` decides to enter a trade if the following conditions are met for a specific trading pair:

1.  **Positive Funding Rate:** The funding rate must be positive and greater than a minimum threshold defined in the configuration. This is the primary profit driver for the arbitrage strategy. The bot aims to collect these funding payments.
2.  **Acceptable Price Spread:** The difference between the futures price and the spot price must be within a predefined range. This ensures that the cost of entering the trade (buying spot and selling futures) does not erase the potential profit from the funding rate.

If both of these conditions are true, the `logic_engine` identifies a profitable arbitrage opportunity and instructs the bot to execute the following trades simultaneously:

*   **Buy** the asset on the **spot market**.
*   **Sell** (short) the asset on the **futures market**.

The position is held to collect the funding payment and is typically closed after a set period (e.g., 8 hours, which is a common funding interval) or if the funding rate turns negative.
