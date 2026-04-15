import asyncio
import sys
import logging

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from pipeline_controller import PipelineController


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_production_run():
    print("\n" + "="*50)
    print("FINAL PRODUCTION TEST RUN: MULTI-PLATFORM AGGREGATOR")
    print("="*50)
    print("Strategy: API-First + JSON-LD + Google Fallback")
    print("Target: 10 events from Hyderabad (Exhaustive Platforms)\n")
    
    controller = PipelineController()
    
    try:
        # We test all platforms sequentially
        results = await controller.run_pipeline(
            location="Hyderabad",
            category=None,
            max_events=10, 
            max_price=None,
            target_platforms=["All Platforms"]
        )
        
        print("\n" + "-"*30)
        print("SUMMARY REPORT")
        print("-"*30)
        print(f"Total Verified Events: {results['total_events']}")
        print(f"Platforms Successfully Reached: {results['platforms_used']}")
        
        print("\nVERIFIED EVENT LISTING:")
        print("-" * 120)
        print("{:<15} | {:<40} | {:<10} | {:<12} | {:<40}".format("Platform", "Event Name", "Price", "Date", "Link"))
        print("-" * 120)
        
        for ev in results['events']:
            # Truncating for display
            name = ev['event_name'][:37] + "..." if len(ev['event_name']) > 40 else ev['event_name']
            link = ev['event_url'][:37] + "..." if len(ev['event_url']) > 40 else ev['event_url']
            price_str = f"INR {ev['price']}"
            print("{:<15} | {:<40} | {:<10} | {:<12} | {:<40}".format(
                ev['platform'], name, price_str, ev['event_date'], link
            ))

            
        print("-" * 120)
            
        if results['total_events'] > 0:
            print("\nFINAL STATUS: SUCCESS - The aggregator is producing live data with mandatory links.")
        else:
            print("\nFINAL STATUS: WARNING - No live events found. Check page hydration or regional availability.")
            
    except Exception as e:
        print(f"\nFINAL STATUS: CRITICAL ERROR - {e}")
        logger.exception(e)

if __name__ == "__main__":
    asyncio.run(test_production_run())
