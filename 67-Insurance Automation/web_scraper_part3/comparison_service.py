"""
Insurance Comparison Service
Aggregates results from all insurance scrapers and saves to database
"""

import concurrent.futures
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import time

from scrapers import get_all_scrapers, InsurancePlan, DurationType
from database import DatabaseManager, init_database


@dataclass
class ProviderResult:
    """Result from a single provider"""
    provider_name: str
    provider_code: str
    provider_color: str
    provider_logo: str
    plans: List[Dict[str, Any]]
    error: Optional[str] = None
    fetch_time: float = 0


class ComparisonService:
    """Service to fetch and compare insurance quotes from all providers"""
    
    def __init__(self):
        self.scrapers = get_all_scrapers()
        # Initialize database
        init_database()
    
    def _fetch_from_provider(self, scraper, params: Dict[str, Any], 
                              request_id: int = None) -> ProviderResult:
        """Fetch quotes from a single provider"""
        start_time = time.time()
        
        try:
            plans = scraper.fetch_quotes(params)
            fetch_time = scraper.fetch_time
            
            provider_info = scraper.get_provider_info()
            
            # Save to database if request_id provided
            if request_id:
                self._save_provider_data(
                    request_id=request_id,
                    scraper=scraper,
                    plans=plans,
                    fetch_time=fetch_time
                )
            
            return ProviderResult(
                provider_name=provider_info["name"],
                provider_code=provider_info["code"],
                provider_color=provider_info["color"],
                provider_logo=provider_info["logo"],
                plans=[plan.to_dict() for plan in plans],
                error=scraper.last_error if not plans else None,
                fetch_time=round(fetch_time, 2)
            )
            
        except Exception as e:
            return ProviderResult(
                provider_name=scraper.PROVIDER_NAME,
                provider_code=scraper.PROVIDER_CODE,
                provider_color=scraper.PROVIDER_COLOR,
                provider_logo=scraper.PROVIDER_LOGO,
                plans=[],
                error=str(e),
                fetch_time=time.time() - start_time
            )
    
    def _save_provider_data(self, request_id: int, scraper, 
                            plans: List[InsurancePlan], fetch_time: float):
        """Save provider response and plans to database"""
        try:
            # Save provider response
            response_id = DatabaseManager.save_provider_response(
                request_id=request_id,
                provider_name=scraper.PROVIDER_NAME,
                provider_code=scraper.PROVIDER_CODE,
                raw_response=scraper.get_raw_response(),
                fetch_time=fetch_time,
                status='success' if plans else 'error',
                error_message=scraper.last_error
            )
            
            # Save each plan
            for plan in plans:
                plan_id = DatabaseManager.save_insurance_plan(
                    response_id=response_id,
                    request_id=request_id,
                    plan_data=plan.to_db_dict()
                )
                
                # Save guarantees for each plan
                for guarantee in plan.guarantees:
                    DatabaseManager.save_plan_guarantee(
                        plan_id=plan_id,
                        guarantee_data={
                            "guarantee_name": guarantee.name,
                            "guarantee_code": guarantee.code,
                            "description": guarantee.description,
                            "capital_guarantee": guarantee.capital,
                            "franchise": guarantee.franchise,
                            "prime_annual": guarantee.prime_annual,
                            "is_included": guarantee.is_included,
                            "is_obligatory": guarantee.is_obligatory,
                            "is_optional": guarantee.is_optional,
                            "has_options": guarantee.has_options,
                            "options": [opt.to_dict() for opt in guarantee.options] if guarantee.options else None,
                            "selected_option": guarantee.selected_option,
                            "display_order": guarantee.order
                        }
                    )
                    
        except Exception as e:
            print(f"Error saving to database: {e}")
    
    def get_all_quotes(self, params: Dict[str, Any], 
                       ip_address: str = None, 
                       user_agent: str = None) -> Dict[str, Any]:
        """
        Fetch quotes from all providers in parallel
        
        Args:
            params: Dictionary with valeur_neuf and valeur_venale
            ip_address: Client IP address (optional)
            user_agent: Client user agent (optional)
            
        Returns:
            Dictionary with all provider results and summary
        """
        total_start = time.time()
        
        # Create database request entry
        request_id = DatabaseManager.create_request(
            valeur_neuf=params.get("valeur_neuf", 0),
            valeur_venale=params.get("valeur_venale", 0),
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        results = []
        
        # Fetch from all providers in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.scrapers)) as executor:
            future_to_scraper = {
                executor.submit(self._fetch_from_provider, scraper, params, request_id): scraper
                for scraper in self.scrapers
            }
            
            for future in concurrent.futures.as_completed(future_to_scraper):
                result = future.result()
                results.append(result)
        
        total_time = time.time() - total_start
        
        # Update request status
        DatabaseManager.update_request_status(
            request_id=request_id,
            status='completed',
            fetch_time=total_time
        )
        
        # Build response
        providers = []
        all_plans = []
        errors = []
        
        for result in results:
            provider_data = {
                "name": result.provider_name,
                "code": result.provider_code,
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
        
        # Find cheapest plans for each duration
        annual_plans = sorted(
            [p for p in all_plans if p.get("is_eligible", True)],
            key=lambda x: x.get("annual", {}).get("prime_total", float('inf'))
        )
        
        semi_annual_plans = sorted(
            [p for p in all_plans if p.get("is_eligible", True)],
            key=lambda x: x.get("semi_annual", {}).get("prime_total", float('inf'))
        )
        
        cheapest_annual = annual_plans[0] if annual_plans else None
        cheapest_semi_annual = semi_annual_plans[0] if semi_annual_plans else None
        
        return {
            "success": len(errors) < len(self.scrapers),
            "request_id": request_id,
            "params": params,
            "providers": providers,
            "summary": {
                "total_plans": len(all_plans),
                "total_providers": len(results),
                "providers_with_results": sum(1 for r in results if r.plans),
                "total_fetch_time": round(total_time, 2),
                "cheapest_annual": {
                    "provider": cheapest_annual.get("provider") if cheapest_annual else None,
                    "plan_name": cheapest_annual.get("plan_name") if cheapest_annual else None,
                    "price": cheapest_annual.get("annual", {}).get("prime_total") if cheapest_annual else None
                },
                "cheapest_semi_annual": {
                    "provider": cheapest_semi_annual.get("provider") if cheapest_semi_annual else None,
                    "plan_name": cheapest_semi_annual.get("plan_name") if cheapest_semi_annual else None,
                    "price": cheapest_semi_annual.get("semi_annual", {}).get("prime_total") if cheapest_semi_annual else None
                }
            },
            "errors": errors if errors else None
        }


def compare_insurance(valeur_neuf: float, valeur_venale: float,
                      ip_address: str = None, user_agent: str = None) -> Dict[str, Any]:
    """
    Convenience function to compare insurance quotes
    
    Args:
        valeur_neuf: New vehicle value in MAD
        valeur_venale: Current vehicle value in MAD
        ip_address: Client IP (optional)
        user_agent: Client user agent (optional)
        
    Returns:
        Comparison results from all providers
    """
    service = ComparisonService()
    return service.get_all_quotes({
        "valeur_neuf": valeur_neuf,
        "valeur_venale": valeur_venale
    }, ip_address, user_agent)
