import argparse
import json
from pathlib import Path

from rag_service.models import SourceFilter
from rag_service.operations import (
    clear_and_rebuild_local_index,
    enum_safe,
    purge_expired_processed_files,
    rebuild_local_index,
    secret_policy_status,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Local operations for the financial RAG service.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    backfill = subcommands.add_parser("backfill", help="Ingest and persist local source data.")
    add_common_ingestion_args(backfill)

    reindex = subcommands.add_parser("reindex", help="Repeatably rebuild the local processed index.")
    add_common_ingestion_args(reindex)
    reindex.add_argument("--clear", action="store_true", help="Delete rag-service/data/processed before rebuilding.")

    retention = subcommands.add_parser("retention", help="Delete processed files older than the retention window.")
    retention.add_argument("--root", default="", help="Processed data root. Defaults to rag-service/data/processed.")
    retention.add_argument("--retention-days", type=int, default=None)

    subcommands.add_parser("secret-status", help="Report required secret names without printing secret values.")

    args = parser.parse_args()
    if args.command == "backfill":
        result = rebuild_local_index(parse_tickers(args.tickers), source_types=parse_source_types(args.sources))
    elif args.command == "reindex":
        tickers = parse_tickers(args.tickers)
        source_types = parse_source_types(args.sources)
        result = clear_and_rebuild_local_index(tickers, source_types=source_types) if args.clear else rebuild_local_index(tickers, source_types=source_types)
    elif args.command == "retention":
        root = Path(args.root) if args.root else None
        result = purge_expired_processed_files(
            root=root or Path(__file__).resolve().parents[2] / "data" / "processed",
            retention_days=args.retention_days,
        )
    else:
        result = secret_policy_status()

    print(json.dumps(enum_safe(result), indent=2, sort_keys=True))


def add_common_ingestion_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tickers", default="NVDA,MSFT", help="Comma-separated ticker list.")
    parser.add_argument("--sources", default="SEC,NEWS,EARNINGS", help="Comma-separated source list.")


def parse_tickers(value: str) -> list[str]:
    return [ticker.strip().upper() for ticker in value.split(",") if ticker.strip()]


def parse_source_types(value: str) -> list[SourceFilter]:
    return [SourceFilter(source.strip().upper()) for source in value.split(",") if source.strip()]


if __name__ == "__main__":
    main()
