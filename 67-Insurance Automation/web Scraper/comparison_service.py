"""
Insurance Comparison Service
Aggregates results from all insurance scrapers
"""

import concurrent.futures
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
import time

from scrapers import AXAScraper, MCMAScraper, RMAScraper, InsurancePlan


@dataclass
class ProviderResult:
    """Result from a single provider"""
    provider_name: str
    provider_color: str
    provider_logo: str
    plans: List[Dict[str, Any]]
    error: str = None
    fetch_time: float = 0


class ComparisonService:
    """Service to fetch and compare insurance quotes from all providers"""
    
    def __init__(self):
        self.scrapers = [
            AXAScraper(),
            MCMAScraper(),
            RMAScraper()
        ]
    
    def _fetch_from_provider(self, scraper, params: Dict[str, Any]) -> ProviderResult:
        """Fetch quotes from a single provider"""
        start_time = time.time()
        
        try:
            plans = scraper.fetch_quotes(params)
            fetch_time = time.time() - start_time
            
            provider_info = scraper.get_provider_info()
            
            return ProviderResult(
                provider_name=provider_info["name"],
                provider_color=provider_info["color"],
                provider_logo=provider_info["logo"],
                plans=[plan.to_dict() for plan in plans],
                error=scraper.last_error if not plans else None,
                fetch_time=round(fetch_time, 2)
            )
            
        except Exception as e:
            return ProviderResult(
                provider_name=scraper.PROVIDER_NAME,
                provider_color=scraper.PROVIDER_COLOR,
                provider_logo=scraper.PROVIDER_LOGO,
                plans=[],
                error=str(e),
                fetch_time=time.time() - start_time
            )
    
    def get_all_quotes(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch quotes from all providers in parallel
        
        Args:
            params: Dictionary with valeur_neuf and valeur_venale
            
        Returns:
            Dictionary with all provider results and summary
        """
        results = []
        total_start = time.time()
        
        # Fetch from all providers in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_scraper = {
                executor.submit(self._fetch_from_provider, scraper, params): scraper
                for scraper in self.scrapers
            }
            
            for future in concurrent.futures.as_completed(future_to_scraper):
                result = future.result()
                results.append(result)
        
        total_time = time.time() - total_start
        
        # Build response
        providers = []
        all_plans = []
        errors = []
        
        for result in results:
            provider_data = {
                "name": result.provider_name,
                "color": result.provider_color,
                "logo": result.provider_logo,
                "plans": result.plans,
                "plan_count": len(result.plans),
                "fetch_time": result.fetch_time
            }
            
            if result.error:
                provider_data["error"] = result.error
                errors.append(f"{result.provider_name}: {result.error}")
            
            providers.append(provider_data)
            all_plans.extend(result.plans)
        
        # Sort all plans by total price
        all_plans_sorted = sorted(all_plans, key=lambda x: x.get("total_price", float('inf')))
        
        # Find cheapest and most expensive
        cheapest = all_plans_sorted[0] if all_plans_sorted else None
        most_expensive = all_plans_sorted[-1] if all_plans_sorted else None
        
        return {
            "success": len(errors) < len(self.scrapers),
            "params": params,
            "providers": providers,
            "summary": {
                "total_plans": len(all_plans),
                "total_providers": len(results),
                "providers_with_results": sum(1 for r in results if r.plans),
                "total_fetch_time": round(total_time, 2),
                "cheapest_plan": cheapest,
                "most_expensive_plan": most_expensive,
                "price_range": {
                    "min": cheapest["total_price"] if cheapest else 0,
                    "max": most_expensive["total_price"] if most_expensive else 0
                }
            },
            "errors": errors if errors else None
        }


def compare_insurance(valeur_neuf: float, valeur_venale: float) -> Dict[str, Any]:
    """
    Convenience function to compare insurance quotes
    
    Args:
        valeur_neuf: New vehicle value in MAD
        valeur_venale: Current vehicle value in MAD
        
    Returns:
        Comparison results from all providers
    """
    service = ComparisonService()
    return service.get_all_quotes({
        "valeur_neuf": valeur_neuf,
        "valeur_venale": valeur_venale
    })
