i want to build a tool with a web user interface to help me determine the quantity to send from our burnaby warehouse to our kentucky warehouse
i want you to help me to first determine what i need in terms of data, what do i need in terms of coding it (best database type, best way to code it)
current way of doing it:
we have a monthly sales report with the combined sales from both the burnaby (Canadian) warehouse and the kentucky (US) warehouse
the excel file contains
sku, sku description, current total quantity, cost, total value, sales by month in multiple columns, supplier for the sku, status (active, discontinued, death row (pending discontinuation if it keeps on performing badly) and other miscellaneous status but the most important ones in terms of this are the active and death row ones, i also have the pending or in transit quantity for each sku (quantity that's been ordered from our suppliers or the pending transfer to the warehouses)
we also have columns that breaks down the sales quantity per warehouse, current quantity per warehouse and pending quantity per warehouse
ask me questions for more details or clarifications




Do you target specific weeks/months of stock coverage per warehouse?
main point is to not run out though that currently seems challenging
check the knowledgebase for best practices on this as im sure i dont have the best way to do it
currently if possible, i look at how much it sold for the last month or last few months then multiply that by 6 then look at the current quantity and pending quantity to determine how much to send
eg. if it sells 100 and the warehouse has 100 current inventory and 200 coming, i will try to send at least 300 but that depends on the inventory we have on the other warehouse
if there are a lot in the other warehouse and i can afford to send more then i will try to send more but always making sure that the other one doesn't run out

Are there minimum/maximum transfer quantities per SKU?
minimum maybe 10
depending on the skus and i try to consider the master carton boxes (we don't really have this data)
but usually it's either a multiple of 25 or 50
eg. for chargers i will do 25, 50, 75 etc
for other ones it will be 50, 100, 150
for best selling ones usually it's multiples of 100

Do you consider transfer costs vs. holding costs?
no
Are there customs/duty considerations for certain SKUs?
no

How often do you make transfers (weekly, bi-weekly, monthly)?
normally depends on if we have enought to fill up a trailer
but preferably monthly
bi weekly if it's busy season and we have shipments that came in

What's the typical transit time from Burnaby to Kentucky?
about a week
but preparing the trailer takes around 2 weeks

Are there minimum shipment sizes to make transfers cost-effective?
preferably a full container but we are looking at lcl
i think this part is less important as the shipping department will tell us if we should send more/have more space

Approximately how many SKUs are you managing?
2000 but will increase to 3-4K

How often is your sales/inventory data updated?
currently with the sheet we have it's monthly
we can do more frequently but it's not setup yet
we have an order management system that we can pull data from daily if needed

Do you need real-time inventory tracking or is daily/weekly updates sufficient?
we would want the current inventory when we are creating the list of skus
but if we're not using the tool not sure we do unless it's for historical data

Is all this data currently in one Excel file, or multiple files?
currently in one excel file
we pull different reports from our OMS (order management system) and then combine them all in the excel file with vlookups and multiple tabs

Do you have any existing systems (ERP, WMS, inventory management) that this tool should integrate with?
later on yes, but i think for now we can just do it as a standalone and we'll upload the needed data via csv files/excel files or through the user interface

How do you currently get notified about low stock situations?
we have a separete daily inventory report and then filter out what's low and compare it to our out of stock list

Who will be using this tool (inventory managers, warehouse staff, executives)?
me and maybe purchasing/inventory staff

Do you need approval workflows for transfers?
not really

Should the tool just recommend quantities or also generate transfer orders?
recommened quantities, be able to edit the recommended quantities, then export the data
the first thing i want to see is the excel file converted into a user interface first with the total sales and the ability to see it broken down into CA and US sales as well and also option to check and uncheck the visible columns and what should be exported
right now i can't really see historical us and ca sales separately as we only do the current month
so if determining what should be sent to kentucky i have to re pull the reports for previous months to double check

Demand forecasting?
in future version maybe

Safety stock calculations?
if needed

Cost optimization (shipping vs holding)?
not neeeded
Alert system for low stock?
not needed right now

Historical transfer performance tracking?
would be nice

What specific problems with your current Excel-based process are you trying to solve? (e.g., time-consuming calculations, human errors, lack of visibility, etc.)
the first thing i want to see is the excel file converted into a user interface first with the total sales and the ability to see it broken down into CA and US sales as well and also option to check and uncheck the visible columns and what should be exported
right now i can't really see historical us and ca sales separately as we only do the current month
so if determining what should be sent to kentucky i have to re pull the reports for previous months to double check
also this will be mainly use to transfer our CA inventory to US
we currently don't do us to ca but we may in the future
it's time consuming, sometimes you miss stuff, hard to get historical data, calculations may not be correct
based on the knowledbase i provided i want to also know the best practices, formulas if any etc

ask me any other further questions or clarifications
you didn't ask about pending quantities i noticed



Pending Quantity Breakdown: You mentioned having pending quantities - could you clarify:

Are these pending arrivals from suppliers (POs already placed)?
yes
Are these inter-warehouse transfers already in transit?
yes
Do you track them separately (supplier orders vs transfers)?
no
How accurate/reliable are your pending quantity dates?
we have the order date
and we can also provide average lead time

Visibility & Updates:

How often are pending quantities updated in your system?
usually monthly after we place an order
the receiving part can be more frequent but it depends on the arrival
once it's received then it wont show up anymore

Do you have visibility on expected arrival dates?
we have the order date
and we can also provide average lead time

Are there frequent delays that affect these pending quantities?
from time to time yes

Current Formula Consideration: When you calculate transfers using "last month sales × 6", do you:

Subtract both current inventory AND pending quantities?
most of the time unless i know that those pending ones are new orders and wont arrive for the next few months then i consider how much we need before then

Only consider pending quantities arriving within a certain timeframe?
i think the above answers that

how are you accounting for stock outs?
like with the monthly sales data
a sku can run out in the middle or beginning of the month so the monthly sales data doesn't accurate reflect what the real demand is


