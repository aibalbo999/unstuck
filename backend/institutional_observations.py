"""Summarize exact-date category observations without filling missing sessions."""
from collections import defaultdict


def summarize_observations(records, ticker, *, limit, rejected_count=0):
    from data_fetch.institutional_provider import institutional_window_status
    dates = sorted({row['date'] for row in records})[-limit:]
    selected = sorted((dict(row) for row in records if row['date'] in dates),
                      key=lambda row: (row['date'], row['category']))
    totals, daily = defaultdict(int), defaultdict(int)
    for row in selected:
        totals[row['category']] += row['net_buy_shares']
        daily[row['date']] += row['net_buy_shares']
    last_five = sum(daily[day] for day in dates[-5:])
    total = sum(totals.values())
    last_status = institutional_window_status(dates, ticker, 5)
    sources = list(dict.fromkeys(row['source'] for row in selected))
    return {'source': ' + '.join(sources), 'lookback_trading_days': len(dates), 'observed_date_count': len(dates),
            'observation_dates': dates, 'window_basis': 'available_observations; not proof of complete exchange sessions',
            'window_coverage_status': institutional_window_status(dates, ticker, limit),
            'last_5_window_status': last_status, 'rejected_record_count': rejected_count,
            'latest_date': dates[-1] if dates else '', 'daily_category_observations': selected,
            'net_buy_shares_by_category': dict(totals),
            'net_buy_thousand_shares_by_category': {key:round(value/1000,2) for key,value in totals.items()},
            'total_net_buy_shares': total, 'total_net_buy_thousand_shares': round(total/1000,2),
            'last_5_trading_days_net_buy_thousand_shares': round(last_five/1000,2) if last_status=='complete' else None,
            'trend': 'accumulation' if total>0 and last_five>0 else 'distribution' if total<0 and last_five<0 else 'mixed',
            'daily_total_net_buy_last_10': [{'date':day,'net_buy_thousand_shares':round(daily[day]/1000,2)}
                                          for day in dates[-10:]]}
