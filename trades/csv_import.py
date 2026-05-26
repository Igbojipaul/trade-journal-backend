import csv
import io
from datetime import datetime
from .models import Trade

REQUIRED_COLUMNS = {'symbol', 'market', 'direction', 'entry_price', 'entry_time'}

VALID_MARKETS = {'forex', 'crypto', 'stocks', 'synthetic'}
VALID_DIRECTIONS = {'long', 'short'}

def parse_csv_trades(file, user) -> dict:
    """
    Parse a CSV file and import trades.
    Returns a summary of imported, skipped, and failed trades.
    """
    imported = []
    skipped = []
    failed = []

    try:
        # Handle both binary and text mode
        if hasattr(file, 'read'):
            content = file.read()
            if isinstance(content, bytes):
                content = content.decode('utf-8-sig')  # handles BOM from Excel
        else:
            content = file

        reader = csv.DictReader(io.StringIO(content))

        # Normalize headers — strip spaces, lowercase
        reader.fieldnames = [
            h.strip().lower().replace(' ', '_')
            for h in (reader.fieldnames or [])
        ]

        # Check required columns exist
        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            return {
                'error': f"Missing required columns: {', '.join(missing)}"
            }

        for i, row in enumerate(reader, start=2):  # start=2 because row 1 is header
            row_num = i

            try:
                # Clean the row
                row = {k: v.strip() if v else '' for k, v in row.items()}

                # Validate market
                market = row.get('market', '').lower()
                if market not in VALID_MARKETS:
                    skipped.append({
                        'row': row_num,
                        'reason': f"Invalid market '{market}'. "
                                  f"Must be one of: {', '.join(VALID_MARKETS)}"
                    })
                    continue

                # Validate direction
                direction = row.get('direction', '').lower()
                if direction not in VALID_DIRECTIONS:
                    skipped.append({
                        'row': row_num,
                        'reason': f"Invalid direction '{direction}'. "
                                  f"Must be 'long' or 'short'"
                    })
                    continue

                # Parse entry time
                entry_time = parse_datetime_flexible(row.get('entry_time', ''))
                if not entry_time:
                    skipped.append({
                        'row': row_num,
                        'reason': f"Could not parse entry_time: "
                                  f"'{row.get('entry_time')}'"
                    })
                    continue

                # Parse optional exit time
                exit_time = parse_datetime_flexible(
                    row.get('exit_time', '')
                ) if row.get('exit_time') else None

                # Build trade object
                trade_data = {
                    'user':        user,
                    'symbol':      row.get('symbol', '').upper(),
                    'market':      market,
                    'direction':   direction,
                    'entry_price': parse_decimal(row.get('entry_price')),
                    'exit_price':  parse_decimal(row.get('exit_price')),
                    'stop_loss':   parse_decimal(row.get('stop_loss')),
                    'take_profit': parse_decimal(row.get('take_profit')),
                    'lot_size':    parse_decimal(row.get('lot_size')) or 1,
                    'pnl':         parse_decimal(row.get('pnl')),
                    'risk_amount': parse_decimal(row.get('risk_amount')),
                    'strategy':    row.get('strategy', ''),
                    'notes':       row.get('notes', ''),
                    'entry_time':  entry_time,
                    'exit_time':   exit_time,
                }

                Trade.objects.create(**trade_data)
                imported.append(row_num)

            except Exception as e:
                failed.append({
                    'row': row_num,
                    'reason': str(e)
                })

        return {
            'imported': len(imported),
            'skipped':  len(skipped),
            'failed':   len(failed),
            'total':    len(imported) + len(skipped) + len(failed),
            'skipped_details': skipped[:10],  # First 10 only
            'failed_details':  failed[:10],
        }

    except Exception as e:
        return {'error': f'Could not read file: {str(e)}'}


def parse_datetime_flexible(value: str):
    """
    Try multiple datetime formats — brokers export dates differently.
    """
    if not value:
        return None

    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d',
        '%d/%m/%Y %H:%M:%S',
        '%d/%m/%Y %H:%M',
        '%d/%m/%Y',
        '%m/%d/%Y %H:%M:%S',
        '%m/%d/%Y',
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue

    return None


def parse_decimal(value):
    """Safely parse a decimal value, return None if empty or invalid."""
    if not value:
        return None
    try:
        # Remove currency symbols and commas
        cleaned = str(value).replace(',', '').replace('$', '').strip()
        return float(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None