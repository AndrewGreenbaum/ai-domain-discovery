"""Test discovery sources configuration"""
import sys

def main():
    print("=== Discovery Sources Test ===\n")

    # Test Brave Search API key
    try:
        from config.settings import settings
        key = settings.brave_search_api_key
        if key:
            print(f"BRAVE_SEARCH_API_KEY: SET ({key[:10]}...)")
        else:
            print("BRAVE_SEARCH_API_KEY: NOT SET")
    except Exception as e:
        print(f"Settings error: {e}")

    print()

    # Test CT log patterns
    try:
        from services.multi_ct_logs import MultiCTLogsService
        ct = MultiCTLogsService()
        print(f"CT Log patterns: {len(ct.CRT_SH_PATTERNS)}")
    except Exception as e:
        print(f"CT Logs error: {e}")

    print()

    # Test startup sources
    try:
        from services.startup_scraper import StartupScraperService
        ss = StartupScraperService()
        print(f"Startup sources: {len(ss.sources)}")
        for name in list(ss.sources.keys())[:5]:
            print(f"  - {name}")
        if len(ss.sources) > 5:
            print(f"  ... and {len(ss.sources) - 5} more")
    except Exception as e:
        print(f"Startup scraper error: {e}")

    print()

    # Test registrar feeds
    try:
        from services.registrar_feeds import registrar_feeds
        print("Registrar feeds: LOADED")
    except Exception as e:
        print(f"Registrar feeds error: {e}")

if __name__ == "__main__":
    main()
