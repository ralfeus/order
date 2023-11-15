import logging

from tqdm import tqdm

def get_all_rates() -> list[dict]:
    logger = logging.getLogger("ems.jobs.get_all_rates()")
    from app.models import Country
    from .models.ems import get_rates
    rates = []
    countries = Country.query.all()
    for country in tqdm(countries):
        try:
            rates += [{'country': country.id, 'weight': r['weight'], 'rate': r['rate']}
                      for r in get_rates(country)]
        except:
            logger.warning(f"Couldn't get rates for {country}")
    return rates