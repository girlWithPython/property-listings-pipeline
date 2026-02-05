"""
Scraper worker tasks - Run third-party property listing portal scraper with automatic geocoding
"""
import asyncio
from workers.celery_app import app
from workers.geocoding import reverse_geocode_missing_postcodes


@app.task(name='workers.scraper_tasks.run_scraper', bind=True)
def run_scraper(self):
    """
    Run the third-party property listing portal scraper as a background task.

    Automatically triggers reverse geocoding after scraping completes.

    Returns:
        dict: Scraper results including:
            - total_found: Total properties found
            - total_inserted: New snapshots created
            - total_skipped: Properties with no changes
            - total_errors: Errors encountered
            - geocoding_task_id: ID of the geocoding task triggered
    """
    print("[SCRAPER WORKER] Starting third-party property listing portal scraper...")

    async def _run_scraper():
        """Run the scraper main function"""
        # Import here to avoid circular dependencies
        from scraper.run import main as scraper_main

        try:
            # Run the scraper
            await scraper_main()

            print("[SCRAPER WORKER] Scraping completed successfully")
            return {"status": "success"}

        except Exception as e:
            print(f"[SCRAPER WORKER ERROR] Scraping failed: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    # Run the async scraper function
    try:
        result = asyncio.run(_run_scraper())
    except RuntimeError as e:
        if "This event loop is already running" in str(e):
            # If running inside an existing event loop (Celery), use nest_asyncio
            import nest_asyncio
            nest_asyncio.apply()
            result = asyncio.run(_run_scraper())
        else:
            raise

    if result["status"] == "success":
        # Trigger reverse geocoding for any new properties
        print("\n[SCRAPER WORKER] Triggering reverse geocoding...")
        geocoding_task = reverse_geocode_missing_postcodes.delay()

        print(f"[SCRAPER WORKER] Geocoding task queued: {geocoding_task.id}")

        return {
            "scraper_status": "success",
            "geocoding_task_id": geocoding_task.id,
            "message": "Scraping completed, geocoding in progress"
        }
    else:
        return {
            "scraper_status": "error",
            "error": result.get("message", "Unknown error"),
            "message": "Scraping failed"
        }


@app.task(name='workers.scraper_tasks.schedule_scraper')
def schedule_scraper():
    """
    Periodic task to run scraper on a schedule.
    Can be run via Celery Beat (e.g., every 6 hours).

    This task chains:
    1. Run scraper
    2. Run reverse geocoding
    3. (Optional) Send email notification

    Returns:
        str: Task ID of the triggered scraper task
    """
    print("[SCHEDULED SCRAPER] Running scheduled scrape...")

    # Trigger the scraper (which will automatically trigger geocoding)
    task = run_scraper.delay()

    print(f"[SCHEDULED SCRAPER] Scraper task queued: {task.id}")

    return {
        "status": "scheduled",
        "scraper_task_id": task.id,
        "message": "Scheduled scraper triggered"
    }
