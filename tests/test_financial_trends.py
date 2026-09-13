"""Labelled quarterly-trend producer: the D5/D6 fix from the NVDA 2026-09-12 review.

The statement fixtures are the payloads the router actually served during that
run, transcribed verbatim from
``~/.tradingagents/logs/NVDA/2026-09-12/message_tool.log`` (the CLI joins a
logged message's lines with spaces, so the two header comments are restored to
their own lines). ``route_to_vendor`` is monkeypatched throughout: nothing here
touches the network.
"""

import unittest
from unittest import mock

import pytest

from tradingagents.agents.utils import financial_trends

pytestmark = pytest.mark.timeout(120)

NVDA_INCOME_QUARTERLY = """\
# Income Statement data for NVDA (quarterly)
# Data retrieved on: 2026-09-12 00:34:00

,2026-07-31,2026-04-30,2026-01-31,2025-10-31,2025-07-31
Tax Effect Of Unusual Items,1282215000.0,0.0,0.0,0.0,343791000.0
Tax Rate For Calcs,0.165,0.165687,0.147585,0.158846,0.153304
Normalized EBITDA,65090000000.0,71002000000.0,51283000000.0,38748000000.0,29690000000.0
Total Unusual Items,7771000000.0,,,,2247000000.0
Total Unusual Items Excluding Goodwill,7771000000.0,,,,2247000000.0
Net Income From Continuing Operation Net Minority Interest,59688000000.0,58321000000.0,42960000000.0,31910000000.0,26422000000.0
Reconciled Depreciation,1127000000.0,997000000.0,812000000.0,751000000.0,669000000.0
Reconciled Cost Of Revenue,24079000000.0,20458000000.0,17034000000.0,15157000000.0,12890000000.0
EBITDA,72861000000.0,71002000000.0,51283000000.0,38748000000.0,31937000000.0
EBIT,71734000000.0,70005000000.0,50471000000.0,37997000000.0,31268000000.0
Net Interest Income,269000000.0,438000000.0,495000000.0,563000000.0,530000000.0
Interest Expense,227000000.0,102000000.0,73000000.0,61000000.0,62000000.0
Interest Income,496000000.0,540000000.0,568000000.0,624000000.0,592000000.0
Normalized Income,53199215000.0,58321000000.0,42960000000.0,31910000000.0,24518791000.0
Net Income From Continuing And Discontinued Operation,59688000000.0,58321000000.0,42960000000.0,31910000000.0,26422000000.0
Total Expenses,32487000000.0,28079000000.0,23828000000.0,20996000000.0,18303000000.0
Total Operating Income As Reported,63734000000.0,53536000000.0,44299000000.0,36010000000.0,28440000000.0
Diluted Average Shares,24285000000.0,24391000000.0,24432000000.0,24483000000.0,24532000000.0
Basic Average Shares,24190000000.0,24286000000.0,24304000000.0,24327000000.0,24366000000.0
Diluted EPS,2.46,2.39,1.76,1.3,1.08
Basic EPS,2.47,2.4,1.77,1.31,1.08
Diluted NI Availto Com Stockholders,59688000000.0,58321000000.0,42960000000.0,31910000000.0,26422000000.0
Net Income Common Stockholders,59688000000.0,58321000000.0,42960000000.0,31910000000.0,26422000000.0
Net Income,59688000000.0,58321000000.0,42960000000.0,31910000000.0,26422000000.0
Net Income Including Noncontrolling Interests,59688000000.0,58321000000.0,42960000000.0,31910000000.0,26422000000.0
Net Income Continuous Operations,59688000000.0,58321000000.0,42960000000.0,31910000000.0,26422000000.0
Tax Provision,11819000000.0,11582000000.0,7438000000.0,6026000000.0,4784000000.0
Pretax Income,71507000000.0,69903000000.0,50398000000.0,37936000000.0,31206000000.0
Other Income Expense,7504000000.0,15929000000.0,5604000000.0,1363000000.0,2236000000.0
Other Non Operating Income Expenses,-267000000.0,15929000000.0,5604000000.0,1363000000.0,-11000000.0
Gain On Sale Of Security,7771000000.0,,,,2247000000.0
Net Non Operating Interest Income Expense,269000000.0,438000000.0,495000000.0,563000000.0,530000000.0
Interest Expense Non Operating,227000000.0,102000000.0,73000000.0,61000000.0,62000000.0
Interest Income Non Operating,496000000.0,540000000.0,568000000.0,624000000.0,592000000.0
Operating Income,63734000000.0,53536000000.0,44299000000.0,36010000000.0,28440000000.0
Operating Expense,8408000000.0,7621000000.0,6794000000.0,5839000000.0,5413000000.0
Research And Development,7054000000.0,6321000000.0,5512000000.0,4705000000.0,4291000000.0
Selling General And Administration,1354000000.0,1300000000.0,1282000000.0,1134000000.0,1122000000.0
Gross Profit,72142000000.0,61157000000.0,51093000000.0,41849000000.0,33853000000.0
Cost Of Revenue,24079000000.0,20458000000.0,17034000000.0,15157000000.0,12890000000.0
Total Revenue,96221000000.0,81615000000.0,68127000000.0,57006000000.0,46743000000.0
Operating Revenue,96221000000.0,81615000000.0,68127000000.0,57006000000.0,46743000000.0
"""

NVDA_BALANCE_QUARTERLY = """\
# Balance Sheet data for NVDA (quarterly)
# Data retrieved on: 2026-09-12 00:34:00

,2026-07-31,2026-04-30,2026-01-31,2025-10-31,2025-07-31,2025-04-30,2025-01-31
Ordinary Shares Number,24147000000.0,24220525225.0,24304000000.0,24305000000.0,24347000000.0,,
Share Issued,24147000000.0,24220525225.0,24304000000.0,24305000000.0,24347000000.0,,
Net Debt,10923000000.0,,,,,,
Total Debt,38351000000.0,12348000000.0,11040000000.0,10481000000.0,10598000000.0,,
Tangible Book Value,204861000000.0,171460000000.0,133155000000.0,111700000000.0,93621000000.0,,
Invested Capital,262350000000.0,203944000000.0,165761000000.0,127364000000.0,108597000000.0,,
Working Capital,154393000000.0,107111000000.0,93442000000.0,90417000000.0,77962000000.0,,
Net Tangible Assets,204861000000.0,171460000000.0,133155000000.0,111700000000.0,93621000000.0,,
Capital Lease Obligations,4985000000.0,3878000000.0,2572000000.0,2014000000.0,2132000000.0,,
Common Stock Equity,228984000000.0,195474000000.0,157293000000.0,118897000000.0,100131000000.0,,
Total Capitalization,261350000000.0,202944000000.0,164762000000.0,126365000000.0,108597000000.0,,
Total Equity Gross Minority Interest,228984000000.0,195474000000.0,157293000000.0,118897000000.0,100131000000.0,,
Stockholders Equity,228984000000.0,195474000000.0,157293000000.0,118897000000.0,100131000000.0,,
Gains Losses Not Affecting Retained Earnings,-25000000.0,137000000.0,178000000.0,339000000.0,170000000.0,,
Other Equity Adjustments,-25000000.0,137000000.0,178000000.0,339000000.0,170000000.0,,
Retained Earnings,219157000000.0,185038000000.0,146973000000.0,107908000000.0,88737000000.0,,
Additional Paid In Capital,9828000000.0,10275000000.0,10118000000.0,10626000000.0,11200000000.0,,
Capital Stock,24000000.0,24000000.0,24000000.0,24000000.0,24000000.0,,
Common Stock,24000000.0,24000000.0,24000000.0,24000000.0,24000000.0,,
Preferred Stock,0.0,0.0,0.0,0.0,0.0,,
Total Liabilities Net Minority Interest,91288000000.0,64000000000.0,49510000000.0,42251000000.0,40609000000.0,,
Total Non Current Liabilities Net Minority Interest,48269000000.0,20116000000.0,17347000000.0,16176000000.0,16352000000.0,,
Other Non Current Liabilities,1901000000.0,737000000.0,381000000.0,376000000.0,243000000.0,,
Tradeand Other Payables Non Current,5602000000.0,4830000000.0,3958000000.0,3532000000.0,3406000000.0,,
Non Current Deferred Liabilities,3415000000.0,3201000000.0,2967000000.0,2786000000.0,2406000000.0,,
Non Current Deferred Revenue,1796000000.0,1403000000.0,1193000000.0,1165000000.0,1055000000.0,,
Non Current Deferred Taxes Liabilities,1619000000.0,1798000000.0,1774000000.0,1621000000.0,1351000000.0,,
Long Term Debt And Capital Lease Obligation,37351000000.0,11348000000.0,10041000000.0,9482000000.0,10297000000.0,,
Long Term Capital Lease Obligation,4985000000.0,3878000000.0,2572000000.0,2014000000.0,1831000000.0,,
Long Term Debt,32366000000.0,7470000000.0,7469000000.0,7468000000.0,8466000000.0,,
Current Liabilities,43019000000.0,43884000000.0,32163000000.0,26075000000.0,24257000000.0,,
Other Current Liabilities,2479000000.0,2194000000.0,1373000000.0,1196000000.0,202000000.0,,
Current Deferred Liabilities,4616000000.0,1714000000.0,1379000000.0,1248000000.0,980000000.0,,
Current Deferred Revenue,4616000000.0,1714000000.0,1379000000.0,1248000000.0,980000000.0,,
Current Debt And Capital Lease Obligation,1000000000.0,1000000000.0,999000000.0,999000000.0,301000000.0,,
Current Capital Lease Obligation,,,,,301000000.0,300000000.0,288000000.0
Current Debt,1000000000.0,1000000000.0,999000000.0,999000000.0,,,
Other Current Borrowings,1000000000.0,1000000000.0,999000000.0,,,,
Current Provisions,2938000000.0,2948000000.0,2807000000.0,2707000000.0,2245000000.0,,
Payables And Accrued Expenses,31986000000.0,36028000000.0,25605000000.0,19925000000.0,20529000000.0,,
Current Accrued Expenses,11721000000.0,12293000000.0,13124000000.0,8386000000.0,9555000000.0,,
Payables,20265000000.0,23735000000.0,12481000000.0,11539000000.0,10974000000.0,,
Total Tax Payable,5206000000.0,10638000000.0,2669000000.0,2915000000.0,1910000000.0,,
Accounts Payable,15059000000.0,13097000000.0,9812000000.0,8624000000.0,9064000000.0,,
Total Assets,320272000000.0,259474000000.0,206803000000.0,161148000000.0,140740000000.0,,
Total Non Current Assets,122860000000.0,108479000000.0,81198000000.0,44656000000.0,38521000000.0,,
Other Non Current Assets,15746000000.0,12733000000.0,8301000000.0,632000000.0,272000000.0,,
Non Current Prepaid Assets,,,,1536000000.0,2103000000.0,2413000000.0,2087000000.0
Non Current Deferred Assets,12159000000.0,11707000000.0,13258000000.0,13674000000.0,13570000000.0,,
Non Current Deferred Taxes Assets,12159000000.0,11707000000.0,13258000000.0,13674000000.0,13570000000.0,,
Non Current Accounts Receivable,,,,1369000000.0,1042000000.0,895000000.0,750000000.0
Investments And Advances,51157000000.0,43364000000.0,22251000000.0,8187000000.0,3799000000.0,,
Investmentin Financial Assets,51157000000.0,43364000000.0,22251000000.0,8187000000.0,3799000000.0,,
Available For Sale Securities,51157000000.0,43364000000.0,22251000000.0,8187000000.0,3799000000.0,,
Goodwill And Other Intangible Assets,24123000000.0,24014000000.0,24138000000.0,7197000000.0,6510000000.0,,
Other Intangible Assets,2998000000.0,3120000000.0,3306000000.0,936000000.0,755000000.0,,
Goodwill,21125000000.0,20894000000.0,20832000000.0,6261000000.0,5755000000.0,,
Net PPE,19675000000.0,16661000000.0,13250000000.0,12061000000.0,11225000000.0,,
Accumulated Depreciation,,,-6587000000.0,,,,-4401000000.0
Gross PPE,19675000000.0,16661000000.0,19837000000.0,12061000000.0,11225000000.0,,
Construction In Progress,,,683000000.0,,,,529000000.0
Other Properties,19675000000.0,16661000000.0,2867000000.0,12061000000.0,11225000000.0,,
Machinery Furniture Equipment,,,12619000000.0,,,,7568000000.0
Buildings And Improvements,,,2891000000.0,,,,2076000000.0
Land And Improvements,,,777000000.0,,,,511000000.0
Properties,,,0.0,,,,0.0
Current Assets,197412000000.0,150995000000.0,125605000000.0,116492000000.0,102219000000.0,,
Other Current Assets,3409000000.0,3916000000.0,3180000000.0,2709000000.0,2658000000.0,,
Restricted Cash,36900000000.0,,,,2800000000.0,1000000000.0,
Inventory,31575000000.0,25797000000.0,21403000000.0,19784000000.0,14962000000.0,,
Finished Goods,6857000000.0,9201000000.0,8774000000.0,6840000000.0,8708000000.0,,
Work In Process,13377000000.0,9949000000.0,8822000000.0,8735000000.0,4411000000.0,,
Raw Materials,11341000000.0,6647000000.0,3807000000.0,4209000000.0,1843000000.0,,
Receivables,63059000000.0,40710000000.0,38466000000.0,33391000000.0,27808000000.0,,
Accounts Receivable,63059000000.0,40710000000.0,38466000000.0,33391000000.0,27808000000.0,,
Cash Cash Equivalents And Short Term Investments,62469000000.0,80572000000.0,62556000000.0,60608000000.0,53991000000.0,,
Other Short Term Investments,40026000000.0,67335000000.0,51951000000.0,49122000000.0,42352000000.0,,
Cash And Cash Equivalents,22443000000.0,13237000000.0,10605000000.0,11486000000.0,11639000000.0,,
"""

NVDA_CASHFLOW_QUARTERLY = """\
# Cash Flow data for NVDA (quarterly)
# Data retrieved on: 2026-09-12 00:34:00

,2026-07-31,2026-04-30,2026-01-31,2025-10-31,2025-07-31,2025-01-31
Free Cash Flow,21400000000.0,48587000000.0,34904000000.0,22115000000.0,13470000000.0,
Repurchase Of Capital Stock,-19732000000.0,-19312000000.0,-3815000000.0,-12456000000.0,-9720000000.0,
Repayment Of Debt,,,0.0,0.0,,0.0
Capital Expenditure,-2677000000.0,-1757000000.0,-1284000000.0,-1636000000.0,-1895000000.0,
Income Tax Paid Supplemental Data,,,6979000000.0,4858000000.0,,4129000000.0
End Cash Position,22443000000.0,13237000000.0,10605000000.0,11486000000.0,11639000000.0,
Beginning Cash Position,13237000000.0,10605000000.0,11486000000.0,11639000000.0,15234000000.0,
Changes In Cash,9206000000.0,2632000000.0,-881000000.0,-153000000.0,-3595000000.0,
Financing Cash Flow,-6176000000.0,-21283000000.0,-6208000000.0,-14880000000.0,-11833000000.0,
Cash Flow From Continuing Financing Activities,-6176000000.0,-21283000000.0,-6208000000.0,-14880000000.0,-11833000000.0,
Net Other Financing Charges,-5293000000.0,-2243000000.0,-2152000000.0,-2453000000.0,-1869000000.0,
Proceeds From Stock Option Exercised,0.0,515000000.0,1000000.0,273000000.0,0.0,
Cash Dividends Paid,-6047000000.0,-243000000.0,-242000000.0,-244000000.0,-244000000.0,
Common Stock Dividend Paid,-6047000000.0,-243000000.0,-242000000.0,-244000000.0,-244000000.0,
Net Common Stock Issuance,-19732000000.0,-19312000000.0,-3815000000.0,-12456000000.0,-9720000000.0,
Common Stock Payments,-19732000000.0,-19312000000.0,-3815000000.0,-12456000000.0,-9720000000.0,
Net Issuance Payments Of Debt,,,0.0,0.0,,0.0
Net Long Term Debt Issuance,,,0.0,0.0,,0.0
Long Term Debt Payments,,,0.0,0.0,,0.0
Investing Cash Flow,-8695000000.0,-26429000000.0,-30861000000.0,-9024000000.0,-7127000000.0,
Cash Flow From Continuing Investing Activities,-8695000000.0,-26429000000.0,-30861000000.0,-9024000000.0,-7127000000.0,
Net Investment Purchase And Sale,-5792000000.0,-24585000000.0,-16412000000.0,-6695000000.0,-4938000000.0,
Sale Of Investment,31807000000.0,1997000000.0,16928000000.0,2730000000.0,3220000000.0,
Purchase Of Investment,-37599000000.0,-26582000000.0,-33340000000.0,-9425000000.0,-8158000000.0,
Net Business Purchase And Sale,-211000000.0,-87000000.0,-13165000000.0,-693000000.0,-294000000.0,
Purchase Of Business,-211000000.0,-87000000.0,-13165000000.0,-693000000.0,-294000000.0,
Net PPE Purchase And Sale,-2677000000.0,-1757000000.0,-1284000000.0,-1636000000.0,-1895000000.0,
Purchase Of PPE,-2677000000.0,-1757000000.0,-1284000000.0,-1636000000.0,-1895000000.0,
Operating Cash Flow,24077000000.0,50344000000.0,36188000000.0,23751000000.0,15365000000.0,
Cash Flow From Continuing Operating Activities,24077000000.0,50344000000.0,36188000000.0,23751000000.0,15365000000.0,
Change In Working Capital,-30708000000.0,3544000000.0,-4325000000.0,-9256000000.0,-11022000000.0,
Change In Other Current Liabilities,753000000.0,1217000000.0,533000000.0,332000000.0,629000000.0,
Change In Payables And Accrued Expense,2167000000.0,9973000000.0,2117000000.0,906000000.0,-2739000000.0,
Change In Accrued Expense,252000000.0,7763000000.0,1053000000.0,1129000000.0,-4053000000.0,
Change In Payable,1915000000.0,2210000000.0,1064000000.0,-223000000.0,1314000000.0,
Change In Account Payable,1915000000.0,2210000000.0,1064000000.0,-223000000.0,1314000000.0,
Change In Prepaid Assets,-5497000000.0,-983000000.0,-280000000.0,-89000000.0,386000000.0,
Change In Inventory,-5784000000.0,-4420000000.0,-1621000000.0,-4823000000.0,-3622000000.0,
Change In Receivables,-22347000000.0,-2243000000.0,-5074000000.0,-5582000000.0,-5676000000.0,
Changes In Account Receivables,-22347000000.0,-2243000000.0,-5074000000.0,-5582000000.0,-5676000000.0,
Other Non Cash Items,316000000.0,-94000000.0,-11000000.0,-80000000.0,-98000000.0,
Stock Based Compensation,2026000000.0,1928000000.0,1633000000.0,1654000000.0,1625000000.0,
Deferred Tax,-602000000.0,1584000000.0,611000000.0,125000000.0,17000000.0,
Deferred Income Tax,-602000000.0,1584000000.0,611000000.0,125000000.0,17000000.0,
Depreciation Amortization Depletion,1127000000.0,997000000.0,812000000.0,751000000.0,669000000.0,
Depreciation And Amortization,1127000000.0,997000000.0,812000000.0,751000000.0,669000000.0,
Operating Gains Losses,-7771000000.0,-15936000000.0,-5492000000.0,-1353000000.0,-2248000000.0,
Gain Loss On Investment Securities,-7771000000.0,-15936000000.0,-5492000000.0,-1353000000.0,-2248000000.0,
Net Income From Continuing Operations,59689000000.0,58321000000.0,42960000000.0,31910000000.0,26422000000.0,
"""

NVDA_INCOME_ANNUAL = """\
# Income Statement data for NVDA (annual)
# Data retrieved on: 2026-09-12 00:35:27

,2026-01-31,2025-01-31,2024-01-31,2023-01-31,2022-01-31
Tax Effect Of Unusual Items,0.0,0.0,0.0,-284130000.0,
Tax Rate For Calcs,0.15117,0.132649,0.12,0.21,
Normalized EBITDA,144552000000.0,86137000000.0,35583000000.0,7339000000.0,
Total Unusual Items,,0.0,0.0,-1353000000.0,0.0
Total Unusual Items Excluding Goodwill,,0.0,0.0,-1353000000.0,0.0
Net Income From Continuing Operation Net Minority Interest,120067000000.0,72880000000.0,29760000000.0,4368000000.0,
Reconciled Depreciation,2843000000.0,1864000000.0,1508000000.0,1543000000.0,
Reconciled Cost Of Revenue,62475000000.0,32639000000.0,16621000000.0,11618000000.0,
EBITDA,144552000000.0,86137000000.0,35583000000.0,5986000000.0,
EBIT,141709000000.0,84273000000.0,34075000000.0,4443000000.0,
Net Interest Income,2041000000.0,1539000000.0,609000000.0,5000000.0,
Interest Expense,259000000.0,247000000.0,257000000.0,262000000.0,
Interest Income,2300000000.0,1786000000.0,866000000.0,267000000.0,
Normalized Income,120067000000.0,72880000000.0,29760000000.0,5436870000.0,
Net Income From Continuing And Discontinued Operation,120067000000.0,72880000000.0,29760000000.0,4368000000.0,
Total Expenses,85551000000.0,49044000000.0,27950000000.0,21397000000.0,
Total Operating Income As Reported,130387000000.0,81453000000.0,32972000000.0,4224000000.0,
Diluted Average Shares,24514000000.0,24804000000.0,24940000000.0,25070000000.0,
Basic Average Shares,24359000000.0,24555000000.0,24690000000.0,24870000000.0,
Diluted EPS,4.9,2.94,1.19,0.174,
Basic EPS,4.93,2.97,1.21,0.176,
Diluted NI Availto Com Stockholders,120067000000.0,72880000000.0,29760000000.0,4368000000.0,
Net Income Common Stockholders,120067000000.0,72880000000.0,29760000000.0,4368000000.0,
Net Income,120067000000.0,72880000000.0,29760000000.0,4368000000.0,
Net Income Including Noncontrolling Interests,120067000000.0,72880000000.0,29760000000.0,4368000000.0,
Net Income Continuous Operations,120067000000.0,72880000000.0,29760000000.0,4368000000.0,
Tax Provision,21383000000.0,11146000000.0,4058000000.0,-187000000.0,
Pretax Income,141450000000.0,84026000000.0,33818000000.0,4181000000.0,
Other Income Expense,9022000000.0,1034000000.0,237000000.0,-1401000000.0,
Other Non Operating Income Expenses,9022000000.0,1034000000.0,237000000.0,-48000000.0,
Special Income Charges,,0.0,0.0,-1353000000.0,0.0
Restructuring And Mergern Acquisition,,0.0,0.0,1353000000.0,0.0
Net Non Operating Interest Income Expense,2041000000.0,1539000000.0,609000000.0,5000000.0,
Interest Expense Non Operating,259000000.0,247000000.0,257000000.0,262000000.0,
Interest Income Non Operating,2300000000.0,1786000000.0,866000000.0,267000000.0,
Operating Income,130387000000.0,81453000000.0,32972000000.0,5577000000.0,
Operating Expense,23076000000.0,16405000000.0,11329000000.0,9779000000.0,
Research And Development,18497000000.0,12914000000.0,8675000000.0,7339000000.0,
Selling General And Administration,4579000000.0,3491000000.0,2654000000.0,2440000000.0,
Gross Profit,153463000000.0,97858000000.0,44301000000.0,15356000000.0,
Cost Of Revenue,62475000000.0,32639000000.0,16621000000.0,11618000000.0,
Total Revenue,215938000000.0,130497000000.0,60922000000.0,26974000000.0,
Operating Revenue,215938000000.0,130497000000.0,60922000000.0,26974000000.0,
"""

# moomoo markdown statements (the shape the other fundamental vendor emits):
# a different format this tool does not parse, and must say so rather than guess.
MOOMOO_INCOME = (
    "## Income Statement \u2014 NVDA\n"
    "### 2027/Q2  (FY 2027, currency: USD)\n"
    "| Item | Value | YoY | QoQ |\n"
    "| --- | --- | --- | --- |\n"
    "| Total Revenue | 96.22B | +105.9% | +17.9% |\n"
)

# A two-column slice of the real quarterly payload (same dates/values): the
# YoY base column is genuinely absent, so YoY must render n/a.
NVDA_INCOME_TWO_COLUMNS = (
    "# Income Statement data for NVDA (quarterly)\n"
    "# Data retrieved on: 2026-09-12 00:34:00\n"
    "\n"
    ",2026-07-31,2026-04-30\n"
    "Total Revenue,96221000000.0,81615000000.0\n"
    "Gross Profit,72142000000.0,61157000000.0\n"
)

# Annual period ends in October: the fiscal-quarter name must follow the data,
# not NVDA's real (January) fiscal calendar.
ANNUAL_ENDS_IN_OCTOBER = (
    "# Income Statement data for TST (annual)\n"
    "# Data retrieved on: 2026-09-12 00:34:00\n"
    "\n"
    ",2026-10-31,2025-10-31,2024-10-31\n"
    "Total Revenue,1000.0,900.0,800.0\n"
)


class _Router:
    """Fake vendor router: answers by (method, frequency), never the network."""

    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    def __call__(self, method, ticker, freq="quarterly", curr_date=None):
        self.calls.append((method, ticker, freq, curr_date))
        if (method, freq) not in self.payloads:
            raise AssertionError(f"unexpected vendor call {method}/{freq}")
        payload = self.payloads[(method, freq)]
        if isinstance(payload, Exception):
            raise payload
        return payload


_QUARTERLY_KEYS = (
    ("get_income_statement", "quarterly"),
    ("get_balance_sheet", "quarterly"),
    ("get_cashflow", "quarterly"),
)


def _router(overrides=None):
    payloads = {
        ("get_income_statement", "quarterly"): NVDA_INCOME_QUARTERLY,
        ("get_balance_sheet", "quarterly"): NVDA_BALANCE_QUARTERLY,
        ("get_cashflow", "quarterly"): NVDA_CASHFLOW_QUARTERLY,
        ("get_income_statement", "annual"): NVDA_INCOME_ANNUAL,
    }
    payloads.update(overrides or {})
    return _Router(payloads)


def _run(router, **kwargs):
    with mock.patch.object(financial_trends, "route_to_vendor", router):
        return financial_trends.get_financial_trends.invoke(
            {"ticker": "NVDA", "curr_date": "2026-09-12", **kwargs}
        )


def _row_cells(report, row_name):
    for line in report.splitlines():
        if line.startswith(f"| {row_name} |"):
            return [cell.strip() for cell in line.strip().strip("|").split("|")]
    raise AssertionError(f"no {row_name!r} row in report:\n{report}")


def _header_cells(report):
    for line in report.splitlines():
        if line.startswith("| Item |"):
            return [cell.strip() for cell in line.strip().strip("|").split("|")]
    raise AssertionError(f"no table header in report:\n{report}")


class FinancialTrendsTests(unittest.TestCase):
    def test_yoy_and_qoq_name_their_periods_and_differ(self):
        """D6 trap: the two delta cells for one item must not be interchangeable."""
        report = _run(_router())
        item, *cells = _row_cells(report, "Total Revenue")
        values, yoy, qoq = cells[:-2], cells[-2], cells[-1]
        self.assertEqual(item, "Total Revenue")
        self.assertEqual(values, [
            "96,221,000,000",
            "81,615,000,000",
            "68,127,000,000",
            "57,006,000,000",
            "46,743,000,000",
        ])
        self.assertEqual(yoy, "+105.9% (Q2 FY26 -> Q2 FY27)")
        self.assertEqual(qoq, "+17.9% (Q1 FY27 -> Q2 FY27)")
        self.assertNotEqual(yoy, qoq)

    def test_period_headers_carry_the_derived_fiscal_quarter(self):
        report = _run(_router())
        self.assertIn("| 2026-07-31 (FY2027 Q2) |", report)
        self.assertIn("| 2026-04-30 (FY2027 Q1) |", report)
        self.assertIn("| 2026-01-31 (FY2026 Q4) |", report)

    def test_fiscal_labels_track_the_vendor_period_ends(self):
        """The label is derived from the data: October annual ends relabel the
        same quarterly columns (FY2026 Q3) instead of assuming a January FY."""
        report = _run(_router({("get_income_statement", "annual"): ANNUAL_ENDS_IN_OCTOBER}))
        self.assertIn("| 2026-07-31 (FY2026 Q3) |", report)

    def test_fiscal_labels_fall_back_to_bare_dates_when_not_derivable(self):
        report = _run(
            _router({("get_income_statement", "annual"): "DATA_UNAVAILABLE: no annual data"})
        )
        self.assertNotIn("(FY", report)
        self.assertIn("| 2026-07-31 |", report)
        self.assertIn("Fiscal-year end could not be derived", report)
        self.assertIn("96,221,000,000", report)
        # still no unlabelled delta: the compared periods are named by date
        yoy = _row_cells(report, "Total Revenue")[-2]
        self.assertEqual(yoy, "+105.9% (2025-07-31 -> 2026-07-31)")

    def test_short_series_yoy_is_na_while_qoq_still_computes(self):
        router = _router({("get_income_statement", "quarterly"): NVDA_INCOME_TWO_COLUMNS})
        report = _run(router, items=["Total Revenue"])
        cells = _row_cells(report, "Total Revenue")
        self.assertEqual(cells[1:3], ["96,221,000,000", "81,615,000,000"])
        self.assertEqual(cells[-2], "n/a (series too short)")
        self.assertEqual(cells[-1], "+17.9% (Q1 FY27 -> Q2 FY27)")

    def test_missing_value_is_na_not_zero(self):
        """A blank or non-finite vendor cell is absent data, never 0.0."""
        payload = (
            "# Balance Sheet data for TST (quarterly)\n"
            ",2026-07-31,2026-04-30\n"
            "Inventory,500.0,\n"
            "Accounts Receivable,nan,400.0\n"
        )
        report = _run(
            _router({("get_balance_sheet", "quarterly"): payload}),
            items=["Inventory", "Accounts Receivable"],
        )
        cells = _row_cells(report, "Inventory")
        self.assertEqual(cells[1], "500.00")
        self.assertEqual(cells[2], "n/a")
        self.assertEqual(cells[-2], "n/a (series too short)")
        self.assertEqual(cells[-1], "n/a (value missing)")
        self.assertEqual(_row_cells(report, "Accounts Receivable")[1], "n/a")

    def test_unparseable_vendor_format_returns_unavailable(self):
        unparseable = dict.fromkeys(
            _QUARTERLY_KEYS + (("get_income_statement", "annual"),), MOOMOO_INCOME
        )
        router = _router(unparseable)
        report = _run(router)
        self.assertTrue(report.startswith("unavailable: "), report)
        self.assertIn("not the yfinance CSV statement shape", report)
        self.assertNotIn("96.22B", report)

    def test_vendor_sentinel_is_echoed_as_unavailable(self):
        sentinel = "DATA_UNAVAILABLE: fundamental_data could not be retrieved (429)."
        sentinels = dict.fromkeys(
            _QUARTERLY_KEYS + (("get_income_statement", "annual"),), sentinel
        )
        router = _router(sentinels)
        report = _run(router)
        self.assertTrue(report.startswith("unavailable: "))
        self.assertIn("DATA_UNAVAILABLE", report)

    def test_one_unparseable_statement_does_not_hide_the_others(self):
        report = _run(_router({("get_balance_sheet", "quarterly"): MOOMOO_INCOME}))
        self.assertIn("| Total Revenue |", report)
        self.assertIn('## Balance Sheet', report)
        self.assertIn("unavailable: get_balance_sheet payload is not the yfinance CSV", report)
        self.assertNotIn("Accounts Receivable", report)

    def test_items_argument_selects_rows_including_cash_flow(self):
        router = _router()
        report = _run(router, items=["Total Revenue", "Free Cash Flow"])
        self.assertIn("| Total Revenue |", report)
        self.assertNotIn("| Gross Profit |", report)
        self.assertNotIn("| Inventory |", report)
        self.assertIn("## Cash Flow", report)
        cells = _row_cells(report, "Free Cash Flow")
        self.assertEqual(cells[1], "21,400,000,000")
        self.assertEqual(cells[-2], "+58.9% (Q2 FY26 -> Q2 FY27)")
        self.assertEqual(cells[-1], "-56.0% (Q1 FY27 -> Q2 FY27)")

    def test_unknown_item_reports_na_instead_of_being_dropped(self):
        report = _run(_router(), items=["Total Revenue", "Nonexistent Metric"])
        self.assertIn("| Total Revenue |", report)
        self.assertIn("n/a Nonexistent Metric: no matching row", report)

    def test_periods_caps_shown_columns_without_losing_the_yoy_delta(self):
        report = _run(_router(), periods=2)
        header = _header_cells(report)
        self.assertEqual(header[0], "Item")
        self.assertEqual(header[1:3], ["2026-07-31 (FY2027 Q2)", "2026-04-30 (FY2027 Q1)"])
        self.assertEqual(header[3:], ["YoY", "QoQ"])
        cells = _row_cells(report, "Total Revenue")
        self.assertEqual(cells[1:3], ["96,221,000,000", "81,615,000,000"])
        self.assertEqual(cells[-2], "+105.9% (Q2 FY26 -> Q2 FY27)")

    def test_balance_sheet_columns_keep_their_own_alignment(self):
        """The balance sheet payload carries an older seventh column; the YoY
        base is still four columns back, not the last column shown."""
        report = _run(_router())
        cells = _row_cells(report, "Cash And Short Term Investments")
        self.assertEqual(cells[-2], "+15.7% (Q2 FY26 -> Q2 FY27)")
        self.assertEqual(cells[-1], "-22.5% (Q1 FY27 -> Q2 FY27)")

    def test_exposes_a_langchain_tool_named_get_financial_trends(self):
        from langchain_core.tools import BaseTool

        self.assertIsInstance(financial_trends.get_financial_trends, BaseTool)
        self.assertEqual(financial_trends.get_financial_trends.name, "get_financial_trends")


if __name__ == "__main__":
    unittest.main()
