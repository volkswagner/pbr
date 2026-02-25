ss_parent_button = "Ship Station";

frappe.ui.form.on("Sales Invoice", {
   refresh(frm) {
      if (frm.doc.status == "Draft") {
         frm.add_custom_button(__("Push to ShipStation"), function (){
            frm.events.create_shipstation_order(frm);
         }, ss_parent_button);

         frm.add_custom_button(__("Fetch Tracking & Amount"), function (){
            frm.events.fetch_shipstation_shipment_info(frm);
         }, ss_parent_button);
      }
   },

   create_shipstation_order(frm) {
      function formatUtcDotNetStyle(posting_date=null) {
         let date = new Date();
         if (posting_date) date = new Date(posting_date);
            
         const pad = (n, size = 2) => String(n).padStart(size, '0');

         return (
            date.getUTCFullYear() + '-' +
            pad(date.getUTCMonth() + 1) + '-' +
            pad(date.getUTCDate()) + 'T' +
            pad(date.getUTCHours()) + ':' +
            pad(date.getUTCMinutes()) + ':' +
            pad(date.getUTCSeconds()) + '.' +
            pad(date.getUTCMilliseconds(), 3) + '0000'
         );
      }

         frappe.call({
            method: "pbr.ss.util.get_address_contact_details",
            freeze: true,
            freeze_message: __("Autopopulating Fields"),
            args: {
               address_name: frm.doc.shipping_address_name,
               contact_name: frm.doc.contact_person
            },
            callback: function (r) {
               if (r.message) {
                  const ship_to_details = r.message;
                  frappe.prompt([
                     {
                        label: __("Order Number (and Key)"),
                        fieldname: "orderNumber",
                        fieldtype: "Data",
                        read_only: 1,
                        default: frm.doc.name
                     },
                     {
                        fieldtype: "Column Break",
                     },
                     {
                        label: __("Order Date"),
                        fieldname: "orderDate",
                        fieldtype: "Date",
                        read_only: 1,
                        default: frm.doc.posting_date
                     },
                     {
                        fieldtype: "Section Break",
                     },
                     {
                        label: __("Name"),
                        fieldname: "name",
                        fieldtype: "Data",
                        default: ship_to_details.full_name,
                        reqd: 1
                     },
                     {
                        label: __("Country"),
                        fieldname: "country",
                        fieldtype: "Data",
                        default: ship_to_details.country,
                        reqd: 1
                     },
                     {
                        label: __("Street 1"),
                        fieldname: "street1",
                        fieldtype: "Data",
                        default: ship_to_details.address_line1,
                        reqd: 1
                     },
                     {
                        label: __("Street 2"),
                        fieldname: "street2",
                        fieldtype: "Data",
                        default: ship_to_details.address_line2
                     },
                     {
                        label: __("Street 3"),
                        fieldname: "street3",
                        fieldtype: "Data",
                     },
                     {
                        fieldtype: "Section Break",
                        hide_border: 1
                     },
                     {
                        label: __("City"),
                        fieldname: "city",
                        fieldtype: "Data",
                        default: ship_to_details.city,
                        reqd: 1
                     },
                     {
                        fieldtype: "Column Break",
                     },
                     {
                        label: __("State/Province"),
                        fieldname: "state",
                        fieldtype: "Data",
                        default: ship_to_details.state,
                        reqd: 1
                     },
                     {
                        fieldtype: "Column Break",
                     },
                     {
                        label: __("Postal Code"),
                        fieldname: "postalCode",
                        fieldtype: "Data",
                        default: ship_to_details.pincode,
                        reqd: 1
                     },
                     {
                        fieldtype: "Section Break",
                     },
                     {
                        label: __("Phone"),
                        fieldname: "phone",
                        fieldtype: "Data",
                        options: "Phone",
                        default: ship_to_details.mobile_no
                     },
                     {
                        label: __("Email"),
                        fieldname: "email",
                        fieldtype: "Data",
                        options: "Email",
                        default: ship_to_details.email_id
                     },
                     {
                        fieldtype: "Section Break",
                        label: `<span class="h4 d-inline-block py-2">${__("International Shipping Declaration")}</span>`,
                        depends_on: `eval: doc.country != "US"`,
                        // collapsible: 1
                     },
                     {
                        label: __("Is International"),
                        fieldname: "isInternational",
                        fieldtype: "Check",
                        hidden: 1,
                        default: ship_to_details.country != "US"
                     },
                     {
                        label: __("Origin Country"),
                        fieldname: "countryOfOrigin",
                        fieldtype: "Data",
                        read_only: 1,
                        default: "US"
                     },
                     {
                        label: __("Description"),
                        fieldname: "description",
                        fieldtype: "Data",
                        read_only: 1,
                        default: "Replacement pinball machine parts"
                     },
                     {
                        label: __("Quantity"),
                        fieldname: "quantity",
                        fieldtype: "Int",
                        read_only: 1,
                        default: 1
                     },
                     {
                        label: __("Item Value"),
                        fieldname: "value",
                        fieldtype: "Currency",
                        read_only: 1,
                        default: frm.doc.grand_total
                     },
                     {
                        label: __("Tariff Code"),
                        fieldname: "harmonizedTariffCode",
                        fieldtype: "Data",
                        read_only: 1,
                        default: "9504.30.00.60"
                     }
                  ],
                  (values) => {
                     frappe.call({
                        method: "pbr.ss.api.create_shipstation_order",
                        freeze: true,
                        freeze_message: __("Pushing to ShipStation"),
                        args: {
                           order_details: values,
                           order_date: formatUtcDotNetStyle(frm.doc.posting_date)
                        }
                     });
                  },
                  "Review Push to ShipStation",
                  "Push"
                  );
               }
            }
         });
   },


	fetch_shipstation_shipment_info(frm) {
    	frappe.call({
        	method: "pbr.ss.api.fetch_shipstation_shipment_info",
        	freeze: true,
        	freeze_message: __("Fetching Tracking and Amount"),
        	args: {
            	invoice_name: frm.doc.name
        	},
        	callback: function(r) { // Added 'r' here to access the response
            	if (r.message) {
                	// 1. Re-fetch the doc from the server to get the updated fields/totals
                	frm.reload_doc();

                	// 2. Visual feedback
                	frappe.show_alert({
                    	message: __("Tracking and Shipping Charges updated from ShipStation"), 
                    	indicator: 'green'
                	});

                	// 3. Scroll to show the user the result
                	frm.scroll_to_field("tracking_num");
            	}
        	}
    	});
	}


});
