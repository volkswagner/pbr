import frappe
from pbr.ss.api import get_ship_from_location

def get_address_details(address_name=None):
   if address_name:
      address_details = frappe.db.get_value("Address", address_name, ["address_line1", "address_line2", "city", "state", "country", "pincode"],as_dict=True)
      address_details["country"] = frappe.db.get_value("Country", address_details["country"], "code").upper()
      
      return address_details

   return {}

def get_contact_details(contact_name=None):
   if contact_name:
      contact_details = frappe.db.get_value("Contact", contact_name, ["first_name", "last_name", "mobile_no", "email_id"],as_dict=True)
      contact_details["full_name"] = f"{contact_details['first_name']} {contact_details['last_name'] or ''}"

      return contact_details
   
   return {}

@frappe.whitelist()
def get_address_contact_details(address_name=None, contact_name=None):
   address_details = get_address_details(address_name)
   contact_details = get_contact_details(contact_name)

   return address_details | contact_details