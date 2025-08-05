import logging
import asyncio
import os

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Teste de ambiente bem-sucedido! O bot iniciou.")
    await asyncio.sleep(10) # Aguarda 10 segundos para o log ser visível
    logger.info("Teste de ambiente concluído. Encerrando.")

if __name__ == "__main__":
    asyncio.run(main())

