from fastapi import HTTPException


def check_product_version(expected, actual):
    if expected is None:
        raise HTTPException(428, detail={'code': 'product_version_required',
                                        'message': 'Read the product and send its version before updating.'})
    if expected != actual:
        raise HTTPException(409, detail={'code': 'product_version_conflict', 'current_version': actual,
                                        'message': 'Product changed. Reload before editing again.'})
