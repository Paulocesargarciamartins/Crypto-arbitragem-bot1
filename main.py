async def check_arbitrage(context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    job = context.job
    chat_id = context.bot_data.get('admin_chat_id')

    try:
        lucro_minimo_porcentagem = context.bot_data.get('lucro_minimo_porcentagem', DEFAULT_LUCRO_MINIMO_PORCENTAGEM)
        trade_amount_usd = context.bot_data.get('trade_amount_usd', DEFAULT_TRADE_AMOUNT_USD)
        fee_percentage = context.bot_data.get('fee_percentage', DEFAULT_FEE_PERCENTAGE)

        if 'active_opportunities' not in context.bot_data:
            context.bot_data['active_opportunities'] = {}

        current_scan_opportunities = {}
        logger.info(f"Iniciando checagem de arbitragem. Lucro mínimo: {lucro_minimo_porcentagem}%, Volume de trade: {trade_amount_usd} USD")

        exchanges_to_scan = {ex_id: instance for ex_id, instance in global_exchanges_instances.items()}

        if len(exchanges_to_scan) < 2:
            logger.error("Não há exchanges suficientes carregadas globalmente para verificar arbitragem.")
            await bot.send_message(chat_id=chat_id, text="Erro: Não foi possível conectar a exchanges suficientes para checar arbitragem.")
            return

        for pair in PAIRS:
            market_data_tasks = []
            for ex_id, exchange in exchanges_to_scan.items():
                market_data_tasks.append(fetch_market_data_for_exchange(exchange, pair, ex_id))

            results = await asyncio.gather(*market_data_tasks, return_exceptions=True)

            market_data = {}
            for result in results:
                if isinstance(result, Exception):
                    logger.warning(f"Erro durante a busca concorrente de dados: {result}")
                elif result:
                    ex_id, data = result
                    market_data[ex_id] = data

            if len(market_data) < 2:
                continue

            best_buy_ex = None
            best_buy_price = float('inf')
            best_buy_volume = 0

            best_sell_ex = None
            best_sell_price = 0.0
            best_sell_volume = 0

            for ex_id, data in market_data.items():
                if data['ask'] < best_buy_price:
                    best_buy_price = data['ask']
                    best_buy_ex = ex_id
                    best_buy_volume = data['ask_volume']

                if data['bid'] > best_sell_price:
                    best_sell_price = data['bid']
                    best_sell_ex = ex_id
                    best_sell_volume = data['bid_volume']

            if best_buy_ex == best_sell_ex:
                logger.debug(f"Melhores preços de compra e venda são na mesma exchange para {pair}. Pulando.")
                continue

            if best_buy_price == 0:
                logger.warning(f"Preço de compra zero para {pair}. Pulando arbitragem.")
                continue

            gross_profit_percentage = ((best_sell_price - best_buy_price) / best_buy_price) * 100

            if gross_profit_percentage > MAX_GROSS_PROFIT_PERCENTAGE_SANITY_CHECK:
                logger.warning(f"Lucro bruto irrealista para {pair} ({gross_profit_percentage:.2f}%). "
                            f"Dados suspeitos: Comprar em {best_buy_ex}: {best_buy_price}, Vender em {best_sell_ex}: {best_sell_price}. Pulando.")
                continue

            net_profit_percentage = gross_profit_percentage - (2 * fee_percentage)

            required_buy_volume = trade_amount_usd / best_buy_price if best_buy_price > 0 else float('inf')
            required_sell_volume = trade_amount_usd / best_sell_price if best_sell_price > 0 else float('inf')

            has_sufficient_liquidity = (
                best_buy_volume >= required_buy_volume and
                best_sell_volume >= required_sell_volume
            )

            if net_profit_percentage >= lucro_minimo_porcentagem and has_sufficient_liquidity:
                opportunity_key = (pair, best_buy_ex, best_sell_ex)
                current_scan_opportunities[opportunity_key] = {
                    'buy_price': best_buy_price,
                    'sell_price': best_sell_price,
                    'net_profit': net_profit_percentage,
                    'volume': trade_amount_usd
                }
            else:
                logger.debug(f"Arbitragem para {pair} não atende aos critérios: "
                            f"Lucro Líquido: {net_profit_percentage:.2f}% (Mínimo: {lucro_minimo_porcentagem}%), "
                            f"Liquidez Suficiente: {has_sufficient_liquidity}")

        opportunities_to_remove_from_active = []
        for key, opp_data in context.bot_data['active_opportunities'].items():
            if key not in current_scan_opportunities:
                opp_data['missed_scans'] = opp_data.get('missed_scans', 0) + 1
                if opp_data['missed_scans'] >= CANCELLATION_CONFIRM_SCANS:
                    pair, buy_ex, sell_ex = key
                    msg = (f"❌ Oportunidade para {pair} (CANCELADA)!\n"
                        f"Anteriormente: Compre em {buy_ex}: {opp_data['buy_price']:.8f}, Venda em {sell_ex}: {opp_data['sell_price']:.8f}\n"
                        f"Lucro Líquido Anterior: {opp_data['net_profit']:.2f}%\n"
                        f"Volume: ${opp_data['volume']:.2f}")
                    logger.info(msg)
                    await bot.send_message(chat_id=chat_id, text=msg)
                    opportunities_to_remove_from_active.append(key)
            else:
                opp_data['missed_scans'] = 0

        for key in opportunities_to_remove_from_active:
            del context.bot_data['active_opportunities'][key]

        for key, current_opp_data in current_scan_opportunities.items():
            pair, buy_ex, sell_ex = key
            last_opp_data = context.bot_data['active_opportunities'].get(key)
            current_time_dt = datetime.now()

            should_alert = False
            if last_opp_data is None:
                should_alert = True
            else:
                profit_diff = abs(current_opp_data['net_profit'] - last_opp_data['net_profit'])
                time_since_last_alert = (current_time_dt - last_opp_data['last_alert_time']).total_seconds()

                if profit_diff >= PROFIT_CHANGE_ALERT_THRESHOLD_PERCENT or time_since_last_alert >= COOLDOWN_PERIOD_FOR_ALERTS:
                    should_alert = True

            if should_alert:
                msg = (f"💰 Arbitragem para {pair} ({current_time_dt.strftime('%H:%M:%S')})!\n"
                    f"Compre em {buy_ex}: {current_opp_data['buy_price']:.8f}\n"
                    f"Venda em {sell_ex}: {current_opp_data['sell_price']:.8f}\n"
                    f"Lucro Líquido: {current_opp_data['net_profit']:.2f}%\n"
                    f"Volume: ${current_opp_data['volume']:.2f}")
                logger.info(msg)
                await bot.send_message(chat_id=chat_id, text=msg)
                context.bot_data['active_opportunities'][key] = {
                    'buy_price': current_opp_data['buy_price'],
                    'sell_price': current_opp_data['sell_price'],
                    'net_profit': current_opp_data['net_profit'],
                    'volume': current_opp_data['volume'],
                    'last_alert_time': current_time_dt,
                    'missed_scans': 0
                }

    except Exception as e:
        logger.error(f"Erro geral na checagem de arbitragem: {e}", exc_info=True)
        if chat_id:
            await bot.send_message(chat_id=chat_id, text=f"Erro crítico na checagem de arbitragem: {e}")

    finally:
        pass
