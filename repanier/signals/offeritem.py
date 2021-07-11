# @receiver(post_init, sender=OfferItem)
# def offer_item_post_init(sender, **kwargs):
#     offer_item = kwargs["instance"]
#     if offer_item.id is None:
#         offer_item.previous_producer_unit_price = DECIMAL_ZERO
#         offer_item.previous_unit_deposit = DECIMAL_ZERO
#     else:
#         offer_item.previous_producer_unit_price = offer_item.producer_unit_price.amount
#         offer_item.previous_unit_deposit = offer_item.unit_deposit.amount


# @receiver(pre_save, sender=OfferItem)
# def offer_item_pre_save(sender, **kwargs):
#     offer_item = kwargs["instance"]
#     # import ipdb
#
#     # ipdb.set_trace()
#     offer_item.recalculate_prices(
#         offer_item.producer_price_are_wo_vat,
#         offer_item.price_list_multiplier,
#     )


# @receiver(post_init, sender=OfferItemSend)
# def offer_item_send_post_init(sender, **kwargs):
#     offer_item_post_init(sender, **kwargs)


# @receiver(pre_save, sender=OfferItemSend)
# def offer_item_send_pre_save(sender, **kwargs):
#     offer_item_pre_save(sender, **kwargs)
