import logging
import time

from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine
from app.services.ai_automation import run_due_daily_automations
from app.services.ollama import OllamaClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_worker() -> None:
    logger.info(
        "AI automation worker started; checking every %s seconds",
        settings.AI_AUTOMATION_POLL_SECONDS,
    )
    ollama = OllamaClient()
    while True:
        try:
            with Session(engine) as session:
                runs = run_due_daily_automations(session, ollama=ollama)
            for run in runs:
                logger.info(
                    "Daily briefing automation %s finished with status %s",
                    run.id,
                    run.status,
                )
        except Exception:
            logger.exception("AI automation check failed")
        time.sleep(settings.AI_AUTOMATION_POLL_SECONDS)


if __name__ == "__main__":
    run_worker()
