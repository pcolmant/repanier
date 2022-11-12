from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    args = "<none>"
    help = "Update DB fields"

    def handle(self, *args, **options):
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE repanier_configuration SET "
                    "group_label_v2 = b.group_label, "
                    "how_to_register_v2 = b.how_to_register, "
                    "offer_customer_mail_v2 = b.offer_customer_mail, "
                    "order_customer_mail_v2 = b.order_customer_mail, "
                    "cancel_order_customer_mail_v2 = b.cancel_order_customer_mail, "
                    "order_staff_mail_v2 = b.order_staff_mail, "
                    "order_producer_mail_v2 = b.order_producer_mail, "
                    "invoice_customer_mail_v2 = b.invoice_customer_mail, "
                    "invoice_producer_mail_v2 = b.invoice_producer_mail "
                    "FROM ( "
                    "  SELECT "
                    "  group_label, "
                    "  how_to_register, "
                    "  offer_customer_mail, "
                    "  order_customer_mail, "
                    "  cancel_order_customer_mail, "
                    "  order_staff_mail, "
                    "  order_producer_mail, "
                    "  invoice_customer_mail, "
                    "  invoice_producer_mail, "
                    "  master_id, "
                    "  language_code "
                    "  FROM repanier_configuration_translation"
                    ") AS b "
                    "WHERE repanier_configuration.id = b.master_id and b.language_code = 'fr' "
                )
                cursor.execute(
                    "UPDATE repanier_deliveryboard SET "
                    "delivery_comment_v2 = b.delivery_comment "
                    "FROM ( "
                    "  SELECT "
                    "  delivery_comment, "
                    "  master_id, "
                    "  language_code "
                    "  FROM repanier_deliveryboard_translation"
                    ") AS b "
                    "WHERE repanier_deliveryboard.id = b.master_id and b.language_code = 'fr' "
                )
                cursor.execute(
                    "UPDATE repanier_lut_productionmode SET "
                    "short_name_v2 = b.short_name, "
                    "description_v2 = b.description "
                    "FROM ( "
                    "  SELECT "
                    "  short_name, "
                    "  description, "
                    "  master_id, "
                    "  language_code "
                    "  FROM repanier_lut_productionmode_translation"
                    ") AS b "
                    "WHERE repanier_lut_productionmode.id = b.master_id and b.language_code = 'fr' "
                )
                cursor.execute(
                    "UPDATE repanier_lut_deliverypoint SET "
                    "short_name_v2 = b.short_name, "
                    "description_v2 = b.description "
                    "FROM ( "
                    "  SELECT "
                    "  short_name, "
                    "  description, "
                    "  master_id, "
                    "  language_code "
                    "  FROM repanier_lut_deliverypoint_translation"
                    ") AS b "
                    "WHERE repanier_lut_deliverypoint.id = b.master_id and b.language_code = 'fr' "
                )
                cursor.execute(
                    "UPDATE repanier_lut_departmentforcustomer SET "
                    "short_name_v2 = b.short_name, "
                    "description_v2 = b.description "
                    "FROM ( "
                    "  SELECT "
                    "  short_name, "
                    "  description, "
                    "  master_id, "
                    "  language_code "
                    "  FROM repanier_lut_departmentforcustomer_translation"
                    ") AS b "
                    "WHERE repanier_lut_departmentforcustomer.id = b.master_id and b.language_code = 'fr' "
                )
                cursor.execute(
                    "UPDATE repanier_lut_permanencerole SET "
                    "short_name_v2 = b.short_name, "
                    "description_v2 = b.description "
                    "FROM ( "
                    "  SELECT "
                    "  short_name, "
                    "  description, "
                    "  master_id, "
                    "  language_code "
                    "  FROM repanier_lut_permanencerole_translation"
                    ") AS b "
                    "WHERE repanier_lut_permanencerole.id = b.master_id and b.language_code = 'fr' "
                )
                cursor.execute(
                    "UPDATE repanier_notification SET "
                    "notification_v2 = b.notification "
                    "FROM ( "
                    "  SELECT "
                    "  notification, "
                    "  master_id, "
                    "  language_code "
                    "  FROM repanier_notification_translation"
                    ") AS b "
                    "WHERE repanier_notification.id = b.master_id and b.language_code = 'fr' "
                )
                cursor.execute(
                    "UPDATE repanier_offeritem SET "
                    "long_name_v2 = b.long_name, "
                    "cache_part_a_v2 = b.cache_part_a, "
                    "cache_part_b_v2 = b.cache_part_b, "
                    "order_sort_order_v2 = b.order_sort_order, "
                    "preparation_sort_order_v2 = b.preparation_sort_order, "
                    "producer_sort_order_v2 = b.producer_sort_order "
                    "FROM ( "
                    "  SELECT "
                    "  long_name, "
                    "  cache_part_a, "
                    "  cache_part_b, "
                    "  order_sort_order, "
                    "  preparation_sort_order, "
                    "  producer_sort_order, "
                    "  master_id, "
                    "  language_code "
                    "  FROM repanier_offeritem_translation"
                    ") AS b "
                    "WHERE repanier_offeritem.id = b.master_id and b.language_code = 'fr' "
                )
                cursor.execute(
                    "UPDATE repanier_permanence SET "
                    "short_name_v2 = b.short_name, "
                    "offer_description_v2 = b.offer_description, "
                    "invoice_description_v2 = b.invoice_description "
                    "FROM ( "
                    "  SELECT "
                    "  short_name, "
                    "  offer_description, "
                    "  invoice_description, "
                    "  master_id, "
                    "  language_code "
                    "  FROM repanier_permanence_translation"
                    ") AS b "
                    "WHERE repanier_permanence.id = b.master_id and b.language_code = 'fr' "
                )
                cursor.execute(
                    "UPDATE repanier_product SET "
                    "long_name_v2 = b.long_name, "
                    "offer_description_v2 = b.offer_description "
                    "FROM ( "
                    "  SELECT "
                    "  long_name, "
                    "  offer_description, "
                    "  master_id, "
                    "  language_code "
                    "  FROM repanier_product_translation"
                    ") AS b "
                    "WHERE repanier_product.id = b.master_id and b.language_code = 'fr' "
                )
                cursor.execute(
                    "UPDATE repanier_product SET "
                    "stock = 0 "
                    "WHERE limit_order_quantity_to_stock = false "
                )
                cursor.execute(
                    "UPDATE repanier_product SET " "stock = 0 " "WHERE stock > 1000 "
                )
                cursor.execute(
                    "UPDATE repanier_staff SET "
                    "long_name_v2 = b.long_name, "
                    "function_description_v2 = b.function_description "
                    "FROM ( "
                    "  SELECT "
                    "  long_name, "
                    "  function_description, "
                    "  master_id, "
                    "  language_code "
                    "  FROM repanier_staff_translation"
                    ") AS b "
                    "WHERE repanier_staff.id = b.master_id and b.language_code = 'fr' "
                )
                # cursor.execute(
                #     "UPDATE repanier_customer SET "
                #     "short_name = short_basket_name, "
                #     "long_name = long_basket_name, "
                #     "is_default = represent_this_buyinggroup, "
                #     "custom_tariff_margin = price_list_multiplier"
                # )
                # cursor.execute(
                #     "UPDATE repanier_producer SET "
                #     "short_name = short_profile_name, "
                #     "long_name = long_profile_name, "
                #     "login_uuid = uuid(uuid), "
                #     "producer_tariff_is_wo_tax = producer_price_are_wo_vat, "
                #     "purchase_margin = price_list_multiplier, "
                #     "invoice_by_customer = invoice_by_basket, "
                #     "is_default = represent_this_buyinggroup"
                # )
                #
                # cursor.execute(
                #     "DELETE FROM repanier_dsp_point"
                # )
                # cursor.execute(
                #     "INSERT INTO repanier_dsp_point (id, is_active, parent_id, lft, rght, tree_id, level, short_name, description, transport, min_transport, group_id, inform_group ) "
                #     "SELECT a.id, a.is_active, a.parent_id, a.lft, a.rght, a.tree_id, a.level, b.short_name, b.description, a.transport, a.min_transport, a.customer_responsible_id as group_id, a.inform_customer_responsible as inform_group "
                #     "  FROM repanier_lut_deliverypoint a, repanier_lut_deliverypoint_translation b "
                #     "  WHERE a.id = b.master_id and b.language_code = 'fr' "
                # )
                # cursor.execute(
                #     "DELETE FROM repanier_label"
                # )
                # cursor.execute(
                #     "INSERT INTO repanier_label (id, is_active, parent_id, lft, rght, tree_id, level, short_name, description, picture ) "
                #     "SELECT a.id, a.is_active, a.parent_id, a.lft, a.rght, a.tree_id, a.level, b.short_name, b.description, a.picture2 as picture "
                #     "  FROM repanier_lut_productionmode a, repanier_lut_productionmode_translation b "
                #     "  WHERE a.id = b.master_id and b.language_code = 'fr' "
                # )
                # cursor.execute(
                #     "UPDATE repanier_product SET "
                #     "name = b.long_name, "
                #     "description = b.offer_description "
                #     "FROM ( "
                #     "  SELECT "
                #     "  offer_description, "
                #     "  long_name,"
                #     "  master_id,"
                #     "  language_code"
                #     "  FROM repanier_product_translation"
                #     ") AS b "
                #     "WHERE repanier_product.id = b.master_id and b.language_code = 'fr' "
                # )
                # cursor.execute(
                #     "DELETE FROM repanier_live_item"
                # )
                # cursor.execute(
                #     "INSERT INTO repanier_live_item ( "
                #     "id, is_active, long_name, offer_description, can_be_ordered, is_updated_on, min_order_qty, inc_order_qty, max_order_qty, "
                #     "department_id, picture, average_weight, producer_price, purchase_price, customer_price, deposit, tax_level "
                #     " ) "
                #     "SELECT a.id, "
                #     "  a.is_active, "
                #     "  a.long_name, "
                #     "  a.offer_description, "
                #     "  a.is_into_offer as can_be_ordered, "
                #     "  a.is_updated_on, "
                #     "  a.customer_minimum_order_quantity as min_order_qty, "
                #     "  a.customer_increment_order_quantity as inc_order_qty, "
                #     "  least(a.stock, 9999.999) as max_order_qty, "
                #     "  a.department_for_customer_id as department_id, "
                #     "  a.picture2 as picture, "
                #     "  a.order_average_weight as average_weight, "
                #     "  a.producer_unit_price as producer_price, "
                #     "  a.producer_unit_price as purchase_price, "
                #     "  a.customer_unit_price as customer_price, "
                #     "  a.unit_deposit as deposit, "
                #     "  a.vat_level as tax_level "
                #     "  FROM repanier_product a "
                # )
                # cursor.execute(
                #     "DELETE FROM repanier_live_item_label"
                # )
                # cursor.execute(
                #     "INSERT INTO repanier_live_item_label (id, liveitem_id, label_id ) "
                #     "SELECT a.id, a.product_id as liveitem_id, a.lut_productionmode_id as label_id "
                #     "  FROM repanier_product_production_mode a "
                # )
                # cursor.execute(
                #     "DELETE FROM repanier_live_item_likes"
                # )
                # cursor.execute(
                #     "INSERT INTO repanier_live_item_likes (id, liveitem_id, label_id ) "
                #     "SELECT a.id, a.product_id as liveitem_id, a.lut_productionmode_id as label_id "
                #     "  FROM repanier_product_likes a "
                # )
                # cursor.execute(
                #     "UPDATE repanier_offeritem SET "
                #     "name = b.long_name, "
                #     "cache_part_a = b.cache_part_a, "
                #     "cache_part_b = b.cache_part_b, "
                #     "order_sort_order = b.order_sort_order, "
                #     "preparation_sort_order = b.preparation_sort_order, "
                #     "producer_sort_order = b.producer_sort_order, "
                #     "FROM ( "
                #     "  SELECT "
                #     "  long_name,"
                #     "  cache_part_a, "
                #     "  cache_part_b, "
                #     "  order_sort_order, "
                #     "  preparation_sort_order, "
                #     "  producer_sort_order, "
                #     "  master_id,"
                #     "  language_code"
                #     "  FROM repanier_offeritem_translation"
                #     ") AS b "
                #     "WHERE repanier_offeritem.id = b.master_id and b.language_code = 'fr' "
                # )
                # cursor.execute(
                #     "DELETE FROM repanier_task"
                # )
                # cursor.execute(
                #     "INSERT INTO repanier_task (id, is_active, parent_id, lft, rght, tree_id, level, short_name, description, is_counted_as_participation, customers_may_register ) "
                #     "SELECT a.id, a.is_active, a.parent_id, a.lft, a.rght, a.tree_id, a.level, b.short_name, b.description, a.is_counted_as_participation, a.customers_may_register "
                #     "  FROM repanier_lut_permanencerole a, repanier_lut_permanencerole_translation b "
                #     "  WHERE a.id = b.master_id and b.language_code = 'fr' "
                # )
                # cursor.execute(
                #     "UPDATE repanier_product SET "
                #     "department_id = NULL "
                # )
                # cursor.execute(
                #     "DELETE FROM repanier_department"
                # )
                # cursor.execute(
                #     "INSERT INTO repanier_department (id, is_active, parent_id, lft, rght, tree_id, level, short_name, description ) "
                #     "SELECT a.id, a.is_active, a.parent_id, a.lft, a.rght, a.tree_id, a.level, b.short_name, b.description "
                #     "  FROM repanier_lut_departmentforcustomer a, repanier_lut_departmentforcustomer_translation b "
                #     "  WHERE a.id = b.master_id and b.language_code = 'fr' "
                # )
                # UPDATE dummy
                # SET customer=subquery.customer,
                #     address=subquery.address,
                #     partn=subquery.partn
                # FROM (SELECT address_id, customer, address, partn
                #       FROM  /* big hairy SQL */ ...) AS subquery
                # WHERE dummy.address_id=subquery.address_id;

                # cursor.execute(
                #     "UPDATE repanier_purchase SET "
                #     "qty = quantity_ordered "
                #     "WHERE status <= '370'"  # ORDER_CLOSED
                # )
                # cursor.execute(
                #     "UPDATE repanier_purchase SET "
                #     "qty = quantity_invoiced "
                #     "WHERE status > '370'"  # ORDER_CLOSED
                # )
                # cursor.execute(
                #     "UPDATE repanier_purchase SET "
                #     "qty_for_preparation_sort_order = quantity_for_preparation_sort_order, "
                #     "qty_for_confirmation = quantity_confirmed, "
                #     "qty_ordered = quantity_ordered, "
                #     "qty_invoiced = quantity_invoiced, "
                #     "purchase_price = producer_unit_price, "
                #     "customer_price = customer_unit_price, "
                #     "sale_price = customer_unit_price, "
                # )
                # cursor.execute(
                #     "UPDATE repanier_deliverypoint SET "
                #     "transport_threshold = transport"
                # )
                # cursor.execute(
                #     "UPDATE repanier_customerinvoice SET "
                #     # "balance_calculated = total_price_with_tax, "
                #     "balance_invoiced = total_price_with_tax, "
                #     "sale_delivery_transport = transport, "
                #     "sale_delivery_min_transport = min_transport, "
                #     "transport = delta_transport, "
                #     "deposit = total_deposit, "
                #     "tax = total_vat, "
                #     "bank_in = bank_amount_in,"
                #     "bank_out = bank_amount_out, "
                #     "date_next_balance = date_balance, "
                #     "next_balance = balance, "
                #     "is_confirmed = is_order_confirm_send, "
                #     "sale_delivery_id = delivery_id"
                # )
                # cursor.execute(
                #     "UPDATE repanier_producerinvoice SET "
                #     "to_be_invoiced = to_be_paid, "
                #     # "balance_calculated = calculated_invoiced_balance, "
                #     "balance_invoiced = to_be_invoiced_balance, "
                #     "reference = invoice_reference, "
                #     "transport = delta_transport, "
                #     "deposit = total_deposit, "
                #     "tax = total_vat, "
                #     "bank_in = bank_amount_in,"
                #     "bank_out = bank_amount_out, "
                #     "date_next_balance = date_balance, "
                #     "next_balance = balance"
                # )
                # cursor.execute(
                #     "UPDATE repanier_customerproducerinvoice SET "
                #     "purchase_price = total_purchase_with_tax "
                # )
                # cursor.execute(
                #     "UPDATE repanier_offeritem SET "
                #     "qty_sold = quantity_invoiced, "
                #     "department_id = department_for_customer_id, "
                #     "picture = picture2, "
                #     "average_weight = order_average_weight, "
                #     "producer_price = producer_unit_price, "
                #     "purchase_price = producer_unit_price, "
                #     "customer_price = customer_unit_price, "
                #     "deposit = unit_deposit, "
                #     "tax_level = vat_level, "
                #     "is_fixed_price = is_resale_price_fixed, "
                #     "is_a_box_content = is_box_content, "
                #     "can_be_sold = may_order"
                # )
                # cursor.execute(
                #     "DELETE FROM repanier_department"
                # )
                # cursor.execute(
                #     "DELETE FROM repanier_department"
                # )
        except:
            pass
