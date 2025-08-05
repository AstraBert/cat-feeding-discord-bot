import os
import asyncio
import random
from logging import getLogger
from dotenv import load_dotenv
from typing import Dict, Any

from supabase import AsyncClient, create_async_client
from discord import Client, Intents

load_dotenv()

logger = getLogger(__name__)

FUNNY_MESSAGES = [
    "El gatito Pumito comió🐈🍲🇪🇸",
    "Der Kater Puma hat gefressen🐈🍲🇩🇪",
    "Кот Пума съел🐈🍲🇷🇺",
    "The demon (our cat), after not being fed for many years (a couple of hours), has finally claimed his terrible meal (a boul of wet food and dry food)🐈🍲😈",
]

CHANNEL_ID = int(os.getenv("CHANNEL_ID"))  # type: ignore
TOKEN = os.getenv("BOT_TOKEN")
intents = Intents.default()
intents.messages = True
bot = Client(intents=intents)

# Global reference to keep tasks alive
background_tasks = set()


@bot.event
async def on_ready() -> None:
    discord_channel = bot.get_channel(CHANNEL_ID)
    if discord_channel:
        logger.debug(
            f"Connected to the channel: {discord_channel.name} ({discord_channel.id})"  # type: ignore
        )

        logger.info(  # type: ignore
            "Status: active✅"
        )
    else:
        logger.error(
            "Unable to find the specified channel ID. Make sure the ID is correct and the bot has the necessary permissions."
        )


async def on_postgres_changes(payload: Dict[str, Any]) -> None:
    logger.debug(f"Received payload: {payload}")
    choice = random.choice(FUNNY_MESSAGES)
    discord_channel = bot.get_channel(CHANNEL_ID)
    if discord_channel:
        logger.debug(
            f"Sending message to channel: {discord_channel.name}  ({discord_channel.id})"  # type: ignore
        )

        try:
            # Send information about the functioning of the bot
            await discord_channel.send(choice)  # type: ignore
            logger.info(f"Successfully sent message: {choice}")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
    else:
        logger.error(
            "Unable to find the specified channel ID. Make sure the ID is correct and the bot has the necessary permissions."
        )


def handle_postgres_changes(payload: Dict[str, Any]) -> None:
    """Synchronous wrapper that properly schedules the async callback"""
    logger.debug("Creating task for postgres changes")

    # Get the current event loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.error("No event loop running when trying to handle postgres changes")
        return

    # Create a task and keep a reference to prevent garbage collection
    task = loop.create_task(on_postgres_changes(payload))
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)


async def setup_supabase_listener() -> AsyncClient:
    """Set up and return the Supabase client with realtime subscription"""
    supa_client: AsyncClient = await create_async_client(
        supabase_key=os.getenv("SUPABASE_KEY"),  # type: ignore
        supabase_url=os.getenv("SUPABASE_URL"),  # type: ignore
    )

    logger.info("Setting up Supabase realtime subscription...")

    try:
        # Subscribe to postgres changes
        _ = (
            await supa_client.channel("feedings")
            .on_postgres_changes(
                "INSERT",  # Listen only to INSERTs
                table="feedings",
                schema="public",
                callback=handle_postgres_changes,
            )
            .subscribe()
        )

        logger.info("Successfully subscribed to Supabase realtime changes")
        return supa_client

    except Exception as e:
        logger.error(f"Failed to set up Supabase subscription: {e}")
        raise


async def main() -> None:
    """Main function to run both Discord bot and Supabase listener concurrently"""
    try:
        # Run both services concurrently
        logger.info("Starting Discord bot and Supabase listener...")

        _ = await setup_supabase_listener()

        # Run the bot concurrently with a keep-alive task
        await asyncio.gather(
            bot.start(token=TOKEN),  # type: ignore
            keep_alive(),  # Keep the event loop running
        )

    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise


async def keep_alive() -> None:
    """Keep the event loop alive for Supabase subscriptions"""
    while True:
        await asyncio.sleep(1)  # Just keep the loop running


if __name__ == "__main__":
    # Set up logging
    import logging

    logging.basicConfig(level=logging.DEBUG)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
