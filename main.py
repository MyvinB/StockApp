"""Main entry point: authenticate with Groww and display portfolio."""

from groww_dashboard.config import GrowwConfig
from groww_dashboard.logging_config import setup_logging
from groww_dashboard.services.portfolio import PortfolioService
from groww_dashboard.services.session_manager import SessionManager


def main():
    setup_logging()
    config = GrowwConfig.from_env()
    session = SessionManager(config)

    try:
        groww = session.login()
        portfolio = PortfolioService(groww)

        print("\n📊 Holdings:\n")
        print(portfolio.get_holdings().to_string(index=False))
        print("\n📈 Summary:", portfolio.summary())
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Error: %s", e)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
