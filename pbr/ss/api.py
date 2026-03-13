import frappe
import base64
import json
import requests
from frappe import _
from dataclasses import dataclass

def generate_headers():
   """
      1. Retrieves the keys from the site configuration
      2. Generates the header
   """
   api_key = frappe.conf.get("ss_api_key")
   api_secret = frappe.conf.get("ss_api_secret")

   if not api_key or not api_secret:
      frappe.throw("ShipStation credentials missing in site_config.json")

   auth_header = base64.b64encode(f"{api_key}:{api_secret}".encode()).decode()
   headers = {"Authorization": f"Basic {auth_header}", "Content-Type": "application/json"}

   return headers

def get_ship_from_location():
   """
      Fetches the Ship From Location from ShipStation
      - the country code is pulled and compared to the Ship To country to determine international shipping
   """
   headers = generate_headers()

   try:
      warehouse_list = requests.get("https://ssapi.shipstation.com/warehouses", headers=headers)
   except Exception as e:
      frappe.log_error(frappe.get_traceback(), _("ShipStation Warehouse List Error"))

   warehouse_list = warehouse_list.json()

   if warehouse_list:
      return warehouse_list[0].get("originAddress")

   return None

@frappe.whitelist()
def create_shipstation_order(order_details, order_date):
   headers = generate_headers()
   order_details = json.loads(order_details)

   # try:
   #    order_list = requests.get("https://ssapi.shipstation.com/orders", headers=headers, params={"orderNumber": order_details.get("orderNumber")})
   # except Exception as e:
   #    frappe.log_error(frappe.get_traceback(), _("ShipStation Order Crosscheck Error"))
   #    frappe.throw(
   #       title=_("Order Crosscheck Failed"),
   #       msg=str(e)
   #    )

   # order_list = order_list.json()
   # if order_list.get("orders"):
   #    frappe.throw(
   #       title=_("Push Failed"),
   #       msg=_("This invoice was already pushed to ShipStation.")
   #    )

   # proceed with push
   payload = {
      "orderNumber": order_details.get("orderNumber"),
      "orderKey": order_details.get("orderNumber"),
      "orderDate": order_date,
      "orderStatus": "awaiting_shipment",
      "shipTo": {
         "name": order_details.get("name"),
         "street1": order_details.get("street1"),
         "street2": order_details.get("street2"),
         "street3": order_details.get("street3"),
         "city": order_details.get("city"),
         "state": order_details.get("state", ""),
         "postalCode": order_details.get("postalCode"),
         "country": order_details.get("country"),
         "phone": order_details.get("phone"),
         "email": order_details.get("email")
      },
      "billTo": {
         "name": order_details.get("name")
      },
      "items": [{"name": "Invoice Items", "quantity": 1}]
   }

   if order_details.get("isInternational"):
      payload["internationalOptions"] = {
         "contents": None,
         "customsItems": [
            {
               "description": order_details.get("description"),
               "quantity": order_details.get("quantity"),
               "value": order_details.get("value"),
               "harmonizedTariffCode": order_details.get("harmonizedTariffCode"),
               "countryOfOrigin": order_details.get("countryOfOrigin")
            }
         ]
      }

   # frappe.throw(str(payload))
   try:
      requests.post("https://ssapi.shipstation.com/orders/createorder", headers=headers, json=payload)
   except Exception as e:
      frappe.log_error(frappe.get_traceback(), _("ShipStation Push Error"))
      frappe.throw(
         title=_("Push Failed"),
         msg=str(e)
      )
      
   frappe.msgprint(
      title=_("Push Successful"),
      msg=_("The order was successfully synced to ShipStation.")
   )

@frappe.whitelist()
def fetch_shipstation_shipment_info(invoice_name, with_shipment_cost=0):
   with_shipment_cost = int(with_shipment_cost)
   frappe.msgprint(_("Starting Fetch for {0}...").format(invoice_name))
   
   headers = generate_headers()
   url = "https://ssapi.shipstation.com/shipments"
   params = {"orderNumber": invoice_name}

   try:
      response = requests.get(url, headers=headers, params=params, timeout=10)
      response.raise_for_status()
      shipment_data = response.json()
   except Exception as e:
      frappe.log_error(frappe.get_traceback(), _("ShipStation API Connection Error"))
      frappe.throw(_("ShipStation Connection Failed: {0}").format(str(e)))

   shipments = shipment_data.get("shipments", [])
   
   if not shipments:
      frappe.msgprint(_("No shipments found in ShipStation for this order number."))
      return {"status": "no_data"}

   # --- THE COST AGGREGATION LOGIC ---
   latest = shipments[0]
   tracking_number = latest.get("trackingNumber")

   doc = frappe.get_doc("Sales Invoice", invoice_name)
   doc.tracking_num = tracking_number

   if with_shipment_cost == 1:
      # Get postage and insurance, defaulting to 0.0 if they are None
      postage_cost = frappe.utils.flt(latest.get("shipmentCost", 0))
      insurance_cost = frappe.utils.flt(latest.get("insuranceCost", 0))
      
      # Combine them to match the "Label Cost" seen in the ShipStation UI
      raw_total_cost = postage_cost + insurance_cost
      
      # Add your $3.00 markup
      markup = 3.00
      final_charge = raw_total_cost + markup

      # --- UPDATE ERPNEXT DOCUMENT ---
      
      shipping_account = "Shipping and Handling - TPR"
      found = False
      for row in doc.taxes:
         if shipping_account in row.account_head:
               row.tax_amount = final_charge
               row.base_tax_amount = final_charge
               found = True
      
      if not found:
         doc.append("taxes", {
               "charge_type": "Actual",
               "account_head": shipping_account,
               "description": "Shipping & Handling (ShipStation Total + $3.00)",
               "tax_amount": final_charge
         })

   doc.save(ignore_permissions=True)
   frappe.db.commit()
   
   # --- SUCCESS MESSAGE WITH BREAKDOWN ---
   msg = _(
      "<b>Successfully Updated!</b><br><br>"
      "<b>Tracking:</b> {0}<br>"
   ).format(tracking_number)

   if with_shipment_cost == 1:
      msg = msg + _(
         "<b>Postage:</b> ${0:,.2f}<br>"
         "<b>Insurance:</b> ${1:,.2f}<br>"
         "<b>Handling:</b> ${2:,.2f}<br>"
         "<b>S & H  Total:</b> ${3:,.2f}"
      ).format(postage_cost or 0, insurance_cost or 0, markup or 0, final_charge or 0)

   
   frappe.msgprint(msg)
   
   return {"status": "success", "tracking": tracking_number}
