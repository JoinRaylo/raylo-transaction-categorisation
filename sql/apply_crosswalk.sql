
-- ============ RAYLO UNIFIED TAXONOMY - crosswalk application (sample test) ============
-- Precedence waterfall (CLAUDE.md section 4): T1 direction overrides -> T2 compound rules ->
-- T3 mechanism-override primaries -> T4 merchant dictionary -> T5 deterministic rules ->
-- T6 provider crosswalk (fallback) -> T7 unclassified.
-- T4 dictionary is a table join, not an inline UNNEST (91k rows / ~4 MB
-- exceeded BigQuery's 1 MB query-length limit). Load with:
--   python src/load_t4_dictionary_bq.py
-- Table: raylo-production.credit_risk_research.merchant_dictionary_t4
WITH sub_xw AS (SELECT * FROM UNNEST([STRUCT<eqx_sub STRING, leaf STRING>
    ('Account Charges','account_charge'),
    ('Account Misuse','account_misuse'),
    ('Accountancy','accountancy'),
    ('Adult Care','adult_care'),
    ('Adult Entertainment','adult_entertainment'),
    ('Advertising Services','advertising_services'),
    ('Airport Parking','airport_parking'),
    ('Airport Spending','airport_spend'),
    ('Alcoholic Beverages Beers and Spirits','alcohol_beer_spirits'),
    ('Alcoholic Beverages Wines','alcohol_wine'),
    ('Amazon','marketplace_amazon'),
    ('Arranged Overdraft','overdraft_arranged'),
    ('Art and Craft','arts_crafts'),
    ('Audio Equipment','audio_equipment'),
    ('BNPL','bnpl'),
    ('Baby Gifts','baby_products'),
    ('Back Market Uk Ltd','marketplace_refurbished'),
    ('Balance Transfer Fees','balance_transfer_fee'),
    ('Bank Interest Accrual','savings_interest_received'),
    ('Bank Transfer','transfer_bank_unspecified'),
    ('Banks And Building Societies','financial_institution_unspecified'),
    ('Bathroom Furniture and Accessories','bathroom'),
    ('Beauty & Massage','beauty_treatment'),
    ('Bedding','bedding'),
    ('Betting','gambling_betting'),
    ('Bikes and Accessories','bicycle'),
    ('Bingo','gambling_bingo'),
    ('Breakdown Cover','breakdown_cover'),
    ('Budgeting and Credit Reporting Services','credit_reporting_service'),
    ('Business Loans','business_loan_repayment'),
    ('Business Services','business_services'),
    ('Cameras and Photography','camera_photography'),
    ('Camping Equipment','camping_equipment'),
    ('Camping Holidays','camping_holiday'),
    ('Car Dealerships','vehicle_purchase'),
    ('Car Finance','car_finance_repayment'),
    ('Car Lease Plan','car_lease'),
    ('Car Parking','car_parking'),
    ('Car Services','vehicle_servicing'),
    ('Card Payment','card_payment_unspecified'),
    ('Career Services','career_services'),
    ('Carwash','carwash'),
    ('Cash & Carry','cash_and_carry'),
    ('Cash Advance Fees','cash_advance_fee'),
    ('Cashback rewards','cashback'),
    ('Catering','catering'),
    ('Charge Card','charge_card_repayment'),
    ('Charity Shops','charity_shop'),
    ('Cheques','cheque'),
    ('Childcare','childcare'),
    ('Childrens Fashion','clothing_childrens'),
    ('Chip Shed Bourton Limited','takeaway'),
    ('Cinema','cinema'),
    ('Cleaning Services','cleaning_services'),
    ('Comic Books','comics'),
    ('Competitions','prize_competitions'),
    ('Computer Peripherals and Accessories','computer_peripherals'),
    ('Computers, Laptops and Tablets','computing_devices'),
    ('Confectionary','confectionary'),
    ('Construction','construction_services'),
    ('Contract Services','business_services'),
    ('Council','council_tax'),
    ('Counselling and Mental Health','mental_health_services'),
    ('Credit Card Fees','credit_card_fee'),
    ('Credit Cards','credit_card_repayment'),
    ('Credit Unions','credit_union_repayment'),
    ('Cryptocurrency','crypto'),
    ('DVD and Blu-ray','physical_media'),
    ('Days Out','days_out'),
    ('Debt Collection','debt_collection'),
    ('Debt Management','debt_management_plan'),
    ('Delivery','delivery_courier'),
    ('Dentist','dentist'),
    ('Department Stores','department_store'),
    ('Direct Debit Repayments','loan_repayment_dd'),
    ('Discount Stores','discount_store'),
    ('Dividend','dividend_received'),
    ('Driving Tuition','driving_tuition'),
    ('Duty Free','airport_spend'),
    ('E-Commerce Payment System','payment_intermediary'),
    ('Electronic Cigarettes','vaping'),
    ('Email Services','email_services'),
    ('Emergency Services','emergency_services'),
    ('Employee Rewards','employee_benefits'),
    ('Employment Agencies','income_agency_work'),
    ('Energy Providers','energy'),
    ('Estate Agents','estate_agent'),
    ('Event Planning','event_planning'),
    ('Experience Days','experience_days'),
    ('Fairtrade and ethical products','groceries_specialist'),
    ('Family History','genealogy_services'),
    ('Family Services','family_services'),
    ('Fancy Dress','fancy_dress'),
    ('Ferries and Rail','ferry_rail_travel'),
    ('Financial Services Other','financial_services_other'),
    ('Flights','flights'),
    ('Footwear','footwear'),
    ('Foreign','foreign_spend_unspecified'),
    ('Foreign Currencies','foreign_currency'),
    ('Foreign Currency','foreign_currency'),
    ('Forex','forex_trading'),
    ('Fragrances','fragrances'),
    ('Fuel','fuel'),
    ('Funeral Directors','funeral'),
    ('Gadgets and Gizmos','gadgets'),
    ('Games and Puzzles','games_puzzles'),
    ('Garages and Parts','vehicle_maintenance'),
    ('Garden Accessories','garden'),
    ('General','services_unspecified'),
    ('General Baby Products','baby_products'),
    ('General Books','books'),
    ('General Car Hire','car_hire'),
    ('General Catalogues','catalogue_retail'),
    ('General Education','education_general'),
    ('General Electrical','electrical_goods'),
    ('General Entertainment','entertainment_other'),
    ('General Fashion','clothing_general'),
    ('General Groceries','groceries'),
    ('General Health and Beauty','health_beauty_general'),
    ('General Insurance','insurance_general'),
    ('General Memberships','memberships'),
    ('Gifts Flowers and Parties','gifts_flowers'),
    ('Glasses and Contact Lenses','optician'),
    ('Government Services','government_services'),
    ('Gyms And Health Clubs','gym_fitness'),
    ('Health Insurance','insurance_health'),
    ('Heating Oil','heating_oil'),
    ('Hire Purchase','hire_purchase_repayment'),
    ('Holiday Cottages and Villas','holiday_rental'),
    ('Holidays','holiday_package'),
    ('Holidays UK','holiday_uk'),
    ('Home Accessories','home_accessories'),
    ('Home Improvements','home_improvement'),
    ('Home Insurance','insurance_home'),
    ('Home Learning','home_learning'),
    ('Hospitals','hospital'),
    ('Hotels and Accommodation','accommodation'),
    ('Hotels and Other Accomodation','accommodation'),
    ('Household Appliances','household_appliances'),
    ('Household Repair Services','home_repair'),
    ('Housing Benefits','housing_benefit'),
    ('ID Cards','id_documents'),
    ('IT Services','it_services'),
    ('Interest Charge','interest_charged'),
    ('International Transfer','transfer_international'),
    ('Internet, TV and Phone','broadband_tv_phone'),
    ('Investments','investment_general'),
    ('Ipswich 5 Star Ltd','takeaway'),
    ('Jewellery and Accesories','jewellery'),
    ('Kitchens and Kitchen Accessories','kitchen'),
    ('Laundry Services','laundry'),
    ('Legal Services','legal_services'),
    ('Life Insurance','insurance_life'),
    ('Lights and Lamps','lighting'),
    ('Lottery','gambling_lottery'),
    ('M.O.T.','vehicle_mot'),
    ('Magazines','magazines'),
    ('Manual Repayment','loan_repayment_manual'),
    ('Marston Holdings','debt_enforcement'),
    ('Maternity Clothing','clothing_maternity'),
    ('Medical','health_other'),
    ('Medicine','medicine'),
    ('Mens Fashion','clothing_mens'),
    ('Mobile Apps and Games','gaming_mobile'),
    ('Mobile Games','gaming_mobile'),
    ('Mobile Handsets and Accessories','mobile_handset'),
    ('Mobile Phone Contracts','mobile_phone_contract'),
    ('Money Management','money_management_service'),
    ('Money Transfer Fees','money_transfer_fee'),
    ('Money Transfers','money_transfer_service'),
    ('Mortgages','mortgage'),
    ('Motor Insurance','insurance_motor'),
    ('Music','music_other'),
    ('Music Tickets','live_music'),
    ('Music and Downloads','streaming'),
    ('Musical Instruments','musical_instruments'),
    ('Newsagents and Convenience Stores','convenience_store'),
    ('Newspapers','newspapers'),
    ('Night Clubs','night_club'),
    ('Office Electricals','office_equipment'),
    ('Office Equipment','office_equipment'),
    ('Office Supplies','office_supplies'),
    ('Online Dating','online_dating'),
    ('Online Games','gaming_online'),
    ('Online Services','online_services'),
    ('Other Insurance','insurance_other'),
    ('Other Travel','travel_other'),
    ('Outdoor Clothing','clothing_outdoor'),
    ('Over 18 Toys','adult_products'),
    ('PC and Console Games','gaming_console_pc'),
    ('Pawn Brokers','pawnbroker'),
    ('Payday Loans','payday_loan'),
    ('Personal Loans','personal_loan_repayment'),
    ('Pet Accessories','pet_supplies'),
    ('Pet Care','veterinary'),
    ('Pet Insurance','insurance_pet'),
    ('Pharmaceuticals','pharmacy'),
    ('Photography Services','photography_services'),
    ('Plants','garden'),
    ('Poker and Casino Games','gambling_casino'),
    ('Political Parties','political_donation'),
    ('Prepaid Cards','prepaid_card'),
    ('Printers, Printer Ink and Printer Toner','printing_supplies'),
    ('Printing','printing_services'),
    ('Private Members Club','private_members_club'),
    ('Property Management','property_management'),
    ('Property Rental','rent'),
    ('Pubs and Bars','pub_bar'),
    ('Recruitment Services','income_agency_work'),
    ('Recycling','waste_services'),
    ('Rejected Payments','returned_payment'),
    ('Restaurants, Cafes and Bistros','restaurant_cafe'),
    ('Retail Finance','retail_finance_repayment'),
    ('Returned Payments','returned_payment'),
    ('Revolving Credit','revolving_credit_repayment'),
    ('Road Tax','road_tax'),
    ('School Fees','school_fees'),
    ('Skin and Hair Care','skin_hair_care'),
    ('Small Retail','retail_small_independent'),
    ('Social Reporting Services','social_reporting'),
    ('Software','software'),
    ('Spares and Repairs','spares_repairs'),
    ('Sporting General','sports_participation'),
    ('Sports Equipment','sports_equipment'),
    ('Sports Ticket','sports_tickets'),
    ('Sportswear','sportswear'),
    ('Stationery','stationery'),
    ('Storage','storage'),
    ('Supplements','supplements'),
    ('TV Licences','tv_licence'),
    ('TV and Online Shopping','retail_tv_online_shopping'),
    ('Take Away','takeaway'),
    ('Taxis','taxi_rideshare'),
    ('Theatre Tickets','theatre'),
    ('Tobacco Products','tobacco'),
    ('Tolls and Crossings','tolls'),
    ('Tools','tools'),
    ('Toy Stores','toys'),
    ('Trade Unions','trade_union'),
    ('Tradesmen','tradesmen'),
    ('Trading','investment_trading'),
    ('Trains and Coaches','public_transport_rail_coach'),
    ('Transfer Mobile App','transfer_mobile_app'),
    ('Transfer Personal','transfer_p2p'),
    ('Travel Guides, Luggage And Accessories','luggage_travel_goods'),
    ('Travel Insurance','insurance_travel'),
    ('Unarranged Overdraft','overdraft_unarranged'),
    ('Vouchers/Discount Codes','vouchers'),
    ('Waste Services','waste_services'),
    ('Water Companies','water'),
    ('Wealth Management','wealth_management'),
    ('Web Services','web_services'),
    ('Weight Loss','weight_loss'),
    ('Womens Fashion','clothing_womens'),
    ('Workwear','clothing_workwear')
])),
pri_xw AS (SELECT * FROM UNNEST([STRUCT<eqx_pri STRING, leaf STRING>
    ('Adjustments','adjustment'),
    ('Amazon All','marketplace_amazon'),
    ('Automotive','transport_other'),
    ('Balance Transfers','balance_transfer'),
    ('Bank Charges and Returns','bank_charge_other'),
    ('Benefits','benefits_state'),
    ('Books, Newspapers and Magazines','books'),
    ('Cash Back','cashback'),
    ('Cash Deposit','cash_deposit'),
    ('Cash Machine','cash_withdrawal'),
    ('Charitable Giving','charitable_donation'),
    ('Commuting and travel','transport_other'),
    ('Education and Learning','education_general'),
    ('Entertainment','entertainment_other'),
    ('Financial Services','financial_services_other'),
    ('Flights and Holidays','travel_other'),
    ('Gambling and Betting','gambling_unspecified'),
    ('Government','government_services'),
    ('Identified Salary','salary'),
    ('Insurance','insurance_general'),
    ('Interest','savings_interest_received'),
    ('Interest Payments','interest_charged'),
    ('Interests and Dividends','savings_interest_received'),
    ('Investments and Trading','investment_general'),
    ('Loans','personal_loan_repayment'),
    ('Misc','unclassified_other'),
    ('Misc Card Spend','unclassified_card_spend'),
    ('Misc Regular Payments','unclassified_recurring'),
    ('Own Transfers','transfer_own_account'),
    ('Pension','pension_contribution'),
    ('Pension Payout','pension_received'),
    ('Personal Healthcare','health_other'),
    ('Pets','pet_other'),
    ('Refund','refund_received'),
    ('Rent and Mortgage','housing_other'),
    ('Restaurants and takeaway','eating_out_other'),
    ('Savings','savings_transfer'),
    ('Services','services_unspecified'),
    ('Shopping (Discretionary)','retail_other'),
    ('Shopping (Fashion)','retail_other'),
    ('Shopping (Home)','retail_other'),
    ('Shopping (Household Essentials)','retail_other'),
    ('Tax','tax_payment'),
    ('Tax Refund','tax_refund'),
    ('Transfers / Other','unclassified_transfer'),
    ('Utilities','utility_other'),
    ('Welfare','benefits_state')
])),
plaid_xw AS (SELECT * FROM UNNEST([STRUCT<plaid_cat STRING, leaf STRING>
    ('BANK_FEES_ATM','account_charge'),
    ('BANK_FEES_FOREIGN_TRANSACTION_FEES','account_charge'),
    ('BANK_FEES_OTHER_BANK_FEES','account_charge'),
    ('BANK_PENALTIES_CASH_ADVANCE_AND_OVERDRAFT_FEES','overdraft_arranged'),
    ('BANK_PENALTIES_INSUFFICIENT_AND_LATE_FEES','returned_payment'),
    ('CHILDCARE_AND_EDUCATION_CHILDCARE_AND_EDUCATION','childcare'),
    ('DINING_COFFEE','restaurant_cafe'),
    ('DINING_DINING','restaurant_cafe'),
    ('DINING_OTHER_DINING','restaurant_cafe'),
    ('DINING_WINE_BARS_AND_PUBS','pub_bar'),
    ('ENTERTAINMENT_CASINOS_AND_GAMBLING','gambling_unspecified'),
    ('ENTERTAINMENT_EVENTS_AND_TICKETS','live_music'),
    ('ENTERTAINMENT_MUSIC_VIDEO_GAMES_TV_AND_MOVIES','entertainment_other'),
    ('ENTERTAINMENT_OTHER_ENTERTAINMENT','entertainment_other'),
    ('FOOD_RETAIL_GROCERIES','groceries'),
    ('FOOD_RETAIL_LIQUOR_STORES','alcohol_beer_spirits'),
    ('FOOD_RETAIL_OTHER','groceries'),
    ('GENERAL_MERCHANDISE_APPAREL_AND_ACCESSORIES','clothing_general'),
    ('GENERAL_MERCHANDISE_COMPUTERS_AND_ELECTRONICS','computing_devices'),
    ('GENERAL_MERCHANDISE_CONVENIENCE_STORES','convenience_store'),
    ('GENERAL_MERCHANDISE_DEPARTMENT_STORES','department_store'),
    ('GENERAL_MERCHANDISE_DISCOUNT_STORES','discount_store'),
    ('GENERAL_MERCHANDISE_FURNITURE_AND_HARDWARE','home_accessories'),
    ('GENERAL_MERCHANDISE_ONLINE_MARKETPLACES','marketplace_general'),
    ('GENERAL_MERCHANDISE_OTHER_GENERAL_MERCHANDISE','retail_other'),
    ('GENERAL_MERCHANDISE_SPORTING_GOODS','sportswear'),
    ('GENERAL_MERCHANDISE_SUPERSTORES','groceries'),
    ('GENERAL_SERVICES_ACCOUNTING_AND_FINANCIAL_SERVICES','financial_services_other'),
    ('GENERAL_SERVICES_CONSULTING_AND_LEGAL_SERVICES','legal_services'),
    ('GENERAL_SERVICES_HOME_IMPROVEMENT_SERVICES','home_improvement'),
    ('GENERAL_SERVICES_OTHER_SERVICES','business_services'),
    ('GENERAL_SERVICES_RELIGIOUS_SERVICES','charitable_donation'),
    ('GOVERNMENTS_AND_NON_PROFIT_DONATIONS','charitable_donation'),
    ('GOVERNMENTS_AND_NON_PROFIT_GOVERNMENTS_AND_NON_PROFIT','council_tax'),
    ('GOVERNMENTS_AND_NON_PROFIT_OTHER_GOVERNMENTS_AND_NON_PROFIT','government_services'),
    ('INCOME_GOVERNMENT_INCOME','benefits_state'),
    ('INCOME_OTHER','income_other_unspecified'),
    ('INCOME_SALARY','salary'),
    ('INSURANCE_AND_TAX_INSURANCE','insurance_general'),
    ('INSURANCE_AND_TAX_TAX_PAYMENT','tax_payment'),
    ('INTERESTS_AND_DIVIDENDS_INTERESTS_AND_DIVIDENDS','savings_interest_received'),
    ('INTEREST_PAYMENTS_INTEREST_CHARGED','interest_charged'),
    ('INTEREST_PAYMENTS_INTEREST_RECEIVED','savings_interest_received'),
    ('LOAN_DISBURSEMENTS_BNPL_AND_EWA','loan_disbursement'),
    ('LOAN_DISBURSEMENTS_CASH_ADVANCES','cash_advance'),
    ('LOAN_DISBURSEMENTS_MORTGAGE_AND_AUTO','loan_disbursement'),
    ('LOAN_DISBURSEMENTS_OTHER','loan_disbursement'),
    ('LOAN_DISBURSEMENTS_PERSONAL','loan_disbursement'),
    ('LOAN_DISBURSEMENTS_STUDENT','loan_disbursement'),
    ('LOAN_PAYMENTS_BNPL_AND_EWA','bnpl'),
    ('LOAN_PAYMENTS_CASH_ADVANCES','cash_advance'),
    ('LOAN_PAYMENTS_CREDIT_CARD_PAYMENT','credit_card_repayment'),
    ('LOAN_PAYMENTS_MORTGAGE_AND_AUTO','mortgage'),
    ('LOAN_PAYMENTS_OTHER','loan_repayment_other'),
    ('LOAN_PAYMENTS_PERSONAL_LOAN_PAYMENT','personal_loan_repayment'),
    ('LOAN_PAYMENTS_STUDENT_LOAN_PAYMENT','student_loan_repayment'),
    ('MEDICAL_DENTAL_AND_VISION','optician'),
    ('MEDICAL_OTHER_MEDICAL','health_other'),
    ('MEDICAL_PHARMACIES_AND_SUPPLEMENTS','pharmacy'),
    ('MEDICAL_PRIMARY_CARE','hospital'),
    ('OTHER_OTHER','unclassified_other'),
    ('PERSONAL_CARE_GYMS_AND_FITNESS_CENTERS','gym_fitness'),
    ('PERSONAL_CARE_HAIR_AND_BEAUTY','skin_hair_care'),
    ('PERSONAL_CARE_OTHER_PERSONAL_CARE','health_beauty_general'),
    ('PET_CARE_AND_SUPPLIES_PET_SUPPLIES','pet_supplies'),
    ('PET_CARE_AND_SUPPLIES_VETERINARY_SERVICES','veterinary'),
    ('RENT_AND_UTILITIES_GAS_AND_ELECTRICITY','energy'),
    ('RENT_AND_UTILITIES_INTERNET_AND_CABLE','broadband_tv_phone'),
    ('RENT_AND_UTILITIES_OTHER_UTILITIES','utility_other'),
    ('RENT_AND_UTILITIES_RENT','rent'),
    ('RENT_AND_UTILITIES_TELECOMMUNICATIONS','mobile_phone_contract'),
    ('RENT_AND_UTILITIES_WATER','water'),
    ('TAX_REFUND_TAX_REFUND','tax_refund'),
    ('TRANSFER_IN_CHECKING','transfer_own_account'),
    ('TRANSFER_IN_CHECKS_AND_ATM','cash_deposit'),
    ('TRANSFER_IN_INVESTMENT_AND_RETIREMENT_FUNDS','investment_general'),
    ('TRANSFER_IN_OTHER','unclassified_transfer'),
    ('TRANSFER_IN_SAVINGS','savings_transfer'),
    ('TRANSFER_IN_TRANSFER_IN_FROM_APPS','transfer_p2p'),
    ('TRANSFER_OUT_CHECKING','transfer_own_account'),
    ('TRANSFER_OUT_CHECKS_AND_ATM','cash_withdrawal'),
    ('TRANSFER_OUT_INVESTMENT_AND_RETIREMENT_FUNDS','investment_general'),
    ('TRANSFER_OUT_OTHER','unclassified_transfer'),
    ('TRANSFER_OUT_SAVINGS','savings_transfer'),
    ('TRANSFER_OUT_TRANSFER_OUT_FROM_APPS','transfer_p2p'),
    ('TRAVEL_AND_TRANSPORTATION_AUTOMOTIVE','vehicle_maintenance'),
    ('TRAVEL_AND_TRANSPORTATION_FLIGHTS','flights'),
    ('TRAVEL_AND_TRANSPORTATION_LODGING','accommodation'),
    ('TRAVEL_AND_TRANSPORTATION_OTHER_TRAVEL_AND_TRANSPORTATION','transport_other'),
    ('TRAVEL_AND_TRANSPORTATION_PUBLIC_TRANSIT','public_transport_rail_coach'),
    ('TRAVEL_AND_TRANSPORTATION_TAXIS_AND_RIDE_SHARES','taxi_rideshare')
])),
dict_xw AS (
  SELECT normalised_merchant AS merchant, detailed_category AS leaf
  FROM `raylo-production.credit_risk_research.merchant_dictionary_t4`
  WHERE review_status = 'approved'
    AND NOT STARTS_WITH(detailed_category, 'unclassified')
),
leaf_meta AS (SELECT * FROM UNNEST([STRUCT<leaf STRING, general_category STRING, necessity STRING,
  cash_flow_type STRING, is_debt_related BOOL, is_priority_debt BOOL, is_age_restricted BOOL, risk_flag STRING>
    ('accommodation','travel_holidays','discretionary','spend',false,false,false,'none'),
    ('account_charge','fees_charges','not_applicable','fee_or_penalty',false,false,false,'none'),
    ('account_misuse','high_cost_distress_credit','not_applicable','fee_or_penalty',false,false,false,'distress_signal'),
    ('accountancy','business_self_employment','mixed_basket','spend',false,false,false,'none'),
    ('adjustment','unclassified','mixed_basket','spend',false,false,false,'none'),
    ('adult_care','health_medical','essential','spend',false,false,false,'none'),
    ('adult_entertainment','entertainment_leisure','discretionary','spend',false,false,true,'none'),
    ('adult_products','entertainment_leisure','discretionary','spend',false,false,true,'none'),
    ('advertising_services','business_self_employment','mixed_basket','spend',false,false,false,'none'),
    ('airport_parking','travel_holidays','discretionary','spend',false,false,false,'none'),
    ('airport_spend','travel_holidays','discretionary','spend',false,false,false,'none'),
    ('alcohol_beer_spirits','groceries_household_essentials','discretionary','spend',false,false,true,'none'),
    ('alcohol_wine','groceries_household_essentials','discretionary','spend',false,false,true,'none'),
    ('arts_crafts','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('audio_equipment','general_retail_marketplaces','discretionary','spend',false,false,false,'none'),
    ('baby_products','general_retail_marketplaces','mixed_basket','spend',false,false,false,'none'),
    ('balance_transfer','credit_loan_repayments','essential','debt_repayment',true,false,false,'none'),
    ('balance_transfer_fee','fees_charges','not_applicable','fee_or_penalty',true,false,false,'none'),
    ('bank_charge_other','fees_charges','not_applicable','fee_or_penalty',false,false,false,'none'),
    ('bathroom','home_garden','mixed_basket','spend',false,false,false,'none'),
    ('beauty_treatment','clothing_personal_care','discretionary','spend',false,false,false,'none'),
    ('bedding','home_garden','mixed_basket','spend',false,false,false,'none'),
    ('benefits_state','income_benefits_state_support','not_applicable','income',false,false,false,'none'),
    ('bicycle','transport_motoring','mixed_basket','spend',false,false,false,'none'),
    ('bnpl','credit_loan_repayments','essential','debt_repayment',true,false,false,'high_cost_credit'),
    ('books','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('breakdown_cover','transport_motoring','essential','spend',false,false,false,'none'),
    ('broadband_tv_phone','utilities_household_bills','essential','spend',false,false,false,'none'),
    ('business_loan_repayment','business_self_employment','essential','debt_repayment',true,false,false,'none'),
    ('business_services','business_self_employment','mixed_basket','spend',false,false,false,'none'),
    ('camera_photography','general_retail_marketplaces','discretionary','spend',false,false,false,'none'),
    ('camping_equipment','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('camping_holiday','travel_holidays','discretionary','spend',false,false,false,'none'),
    ('car_finance_repayment','credit_loan_repayments','essential','debt_repayment',true,false,false,'none'),
    ('car_hire','transport_motoring','discretionary','spend',false,false,false,'none'),
    ('car_lease','credit_loan_repayments','essential','debt_repayment',true,false,false,'none'),
    ('car_parking','transport_motoring','essential','spend',false,false,false,'none'),
    ('card_payment_unspecified','transfers','not_applicable','transfer_own_accounts',false,false,false,'none'),
    ('career_services','childcare_education','discretionary','spend',false,false,false,'none'),
    ('carwash','transport_motoring','discretionary','spend',false,false,false,'none'),
    ('cash_advance','high_cost_distress_credit','essential','debt_repayment',true,false,false,'high_cost_credit'),
    ('cash_advance_fee','high_cost_distress_credit','not_applicable','fee_or_penalty',false,false,false,'distress_fee'),
    ('cash_and_carry','groceries_household_essentials','essential','spend',false,false,false,'none'),
    ('cash_deposit','cash','not_applicable','transfer_own_accounts',false,false,false,'visibility_loss'),
    ('cash_withdrawal','cash','not_applicable','transfer_own_accounts',false,false,false,'visibility_loss'),
    ('cashback','income_other','not_applicable','income',false,false,false,'none'),
    ('catalogue_retail','general_retail_marketplaces','mixed_basket','spend',false,false,false,'none'),
    ('catering','eating_drinking_out','discretionary','spend',false,false,false,'none'),
    ('charge_card_repayment','credit_loan_repayments','essential','debt_repayment',true,false,false,'none'),
    ('charitable_donation','charitable_political_giving','discretionary','spend',false,false,false,'none'),
    ('charity_shop','charitable_political_giving','discretionary','spend',false,false,false,'none'),
    ('cheque','transfers','not_applicable','transfer_own_accounts',false,false,false,'none'),
    ('childcare','childcare_education','essential','spend',false,false,false,'none'),
    ('cinema','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('cleaning_services','home_garden','discretionary','spend',false,false,false,'none'),
    ('clothing_childrens','clothing_personal_care','mixed_basket','spend',false,false,false,'none'),
    ('clothing_general','clothing_personal_care','mixed_basket','spend',false,false,false,'none'),
    ('clothing_maternity','clothing_personal_care','mixed_basket','spend',false,false,false,'none'),
    ('clothing_mens','clothing_personal_care','mixed_basket','spend',false,false,false,'none'),
    ('clothing_outdoor','clothing_personal_care','discretionary','spend',false,false,false,'none'),
    ('clothing_womens','clothing_personal_care','mixed_basket','spend',false,false,false,'none'),
    ('clothing_workwear','clothing_personal_care','essential','spend',false,false,false,'none'),
    ('comics','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('computer_peripherals','general_retail_marketplaces','mixed_basket','spend',false,false,false,'none'),
    ('computing_devices','general_retail_marketplaces','mixed_basket','spend',false,false,false,'none'),
    ('confectionary','groceries_household_essentials','discretionary','spend',false,false,false,'none'),
    ('construction_services','home_garden','mixed_basket','spend',false,false,false,'none'),
    ('convenience_store','groceries_household_essentials','mixed_basket','spend',false,false,false,'none'),
    ('council_tax','council_tax_government','essential','spend',false,true,false,'none'),
    ('credit_card_fee','fees_charges','not_applicable','fee_or_penalty',true,false,false,'none'),
    ('credit_card_repayment','credit_loan_repayments','essential','debt_repayment',true,false,false,'none'),
    ('credit_reporting_service','high_cost_distress_credit','discretionary','spend',false,false,false,'distress_signal'),
    ('credit_union_repayment','credit_loan_repayments','essential','debt_repayment',true,false,false,'none'),
    ('crypto','savings_investments','not_applicable','transfer_own_accounts',false,false,false,'speculative_asset'),
    ('days_out','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('debt_collection','high_cost_distress_credit','essential','debt_repayment',true,false,false,'distress_signal'),
    ('debt_enforcement','high_cost_distress_credit','essential','debt_repayment',true,false,false,'distress_signal'),
    ('debt_management_plan','high_cost_distress_credit','essential','debt_repayment',true,false,false,'distress_signal'),
    ('delivery_courier','general_retail_marketplaces','mixed_basket','spend',false,false,false,'none'),
    ('dentist','health_medical','essential','spend',false,false,false,'none'),
    ('department_store','general_retail_marketplaces','mixed_basket','spend',false,false,false,'none'),
    ('discount_store','groceries_household_essentials','essential','spend',false,false,false,'none'),
    ('dividend_received','income_other','not_applicable','income',false,false,false,'none'),
    ('driving_tuition','childcare_education','discretionary','spend',false,false,false,'none'),
    ('eating_out_other','eating_drinking_out','discretionary','spend',false,false,false,'none'),
    ('education_general','childcare_education','essential','spend',false,false,false,'none'),
    ('electrical_goods','general_retail_marketplaces','mixed_basket','spend',false,false,false,'none'),
    ('email_services','digital_subscriptions_services','discretionary','spend',false,false,false,'none'),
    ('emergency_services','council_tax_government','essential','spend',false,false,false,'none'),
    ('employee_benefits','income_employment','not_applicable','income',false,false,false,'none'),
    ('energy','utilities_household_bills','essential','spend',false,true,false,'none'),
    ('entertainment_other','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('estate_agent','housing','mixed_basket','spend',false,false,false,'none'),
    ('event_planning','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('experience_days','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('family_services','health_medical','essential','spend',false,false,false,'none'),
    ('fancy_dress','clothing_personal_care','discretionary','spend',false,false,false,'none'),
    ('ferry_rail_travel','travel_holidays','discretionary','spend',false,false,false,'none'),
    ('financial_institution_unspecified','unclassified','mixed_basket','spend',false,false,false,'none'),
    ('financial_services_other','credit_loan_repayments','mixed_basket','spend',false,false,false,'none'),
    ('flights','travel_holidays','discretionary','spend',false,false,false,'none'),
    ('footwear','clothing_personal_care','mixed_basket','spend',false,false,false,'none'),
    ('foreign_currency','travel_holidays','discretionary','spend',false,false,false,'none'),
    ('foreign_spend_unspecified','travel_holidays','mixed_basket','spend',false,false,false,'none'),
    ('forex_trading','savings_investments','not_applicable','transfer_own_accounts',false,false,false,'speculative_asset'),
    ('fragrances','clothing_personal_care','discretionary','spend',false,false,false,'none'),
    ('fuel','transport_motoring','essential','spend',false,false,false,'none'),
    ('funeral','health_medical','essential','spend',false,false,false,'none'),
    ('gadgets','general_retail_marketplaces','discretionary','spend',false,false,false,'none'),
    ('gambling_betting','gambling','discretionary','spend',false,false,true,'behavioural_risk'),
    ('gambling_bingo','gambling','discretionary','spend',false,false,true,'behavioural_risk'),
    ('gambling_casino','gambling','discretionary','spend',false,false,true,'behavioural_risk'),
    ('gambling_lottery','gambling','discretionary','spend',false,false,true,'low_stakes_gambling'),
    ('gambling_unspecified','gambling','discretionary','spend',false,false,true,'behavioural_risk'),
    ('games_puzzles','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('gaming_console_pc','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('gaming_mobile','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('gaming_online','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('garden','home_garden','discretionary','spend',false,false,false,'none'),
    ('genealogy_services','digital_subscriptions_services','discretionary','spend',false,false,false,'none'),
    ('gifts_flowers','general_retail_marketplaces','discretionary','spend',false,false,false,'none'),
    ('government_services','council_tax_government','essential','spend',false,false,false,'none'),
    ('groceries','groceries_household_essentials','essential','spend',false,false,false,'none'),
    ('groceries_specialist','groceries_household_essentials','essential','spend',false,false,false,'none'),
    ('gym_fitness','health_medical','discretionary','spend',false,false,false,'none'),
    ('health_beauty_general','clothing_personal_care','discretionary','spend',false,false,false,'none'),
    ('health_other','health_medical','essential','spend',false,false,false,'none'),
    ('heating_oil','utilities_household_bills','essential','spend',false,true,false,'none'),
    ('hire_purchase_repayment','credit_loan_repayments','essential','debt_repayment',true,false,false,'none'),
    ('holiday_package','travel_holidays','discretionary','spend',false,false,false,'none'),
    ('holiday_rental','travel_holidays','discretionary','spend',false,false,false,'none'),
    ('holiday_uk','travel_holidays','discretionary','spend',false,false,false,'none'),
    ('home_accessories','home_garden','mixed_basket','spend',false,false,false,'none'),
    ('home_improvement','home_garden','mixed_basket','spend',false,false,false,'none'),
    ('home_learning','childcare_education','essential','spend',false,false,false,'none'),
    ('home_repair','home_garden','essential','spend',false,false,false,'none'),
    ('hospital','health_medical','essential','spend',false,false,false,'none'),
    ('household_appliances','home_garden','mixed_basket','spend',false,false,false,'none'),
    ('housing_benefit','income_benefits_state_support','not_applicable','income',false,false,false,'none'),
    ('housing_other','housing','essential','spend',false,false,false,'none'),
    ('id_documents','council_tax_government','essential','spend',false,false,false,'none'),
    ('income_agency_work','income_employment','not_applicable','income',false,false,false,'none'),
    ('income_other_unspecified','income_other','not_applicable','income',false,false,false,'none'),
    ('insurance_general','insurance','essential','spend',false,false,false,'none'),
    ('insurance_health','insurance','essential','spend',false,false,false,'none'),
    ('insurance_home','insurance','essential','spend',false,false,false,'none'),
    ('insurance_life','insurance','essential','spend',false,false,false,'none'),
    ('insurance_motor','insurance','essential','spend',false,false,false,'none'),
    ('insurance_other','insurance','essential','spend',false,false,false,'none'),
    ('insurance_pet','pets','discretionary','spend',false,false,false,'none'),
    ('insurance_travel','insurance','discretionary','spend',false,false,false,'none'),
    ('interest_charged','fees_charges','not_applicable','fee_or_penalty',true,false,false,'none'),
    ('investment_general','savings_investments','not_applicable','transfer_own_accounts',false,false,false,'none'),
    ('investment_trading','savings_investments','not_applicable','transfer_own_accounts',false,false,false,'none'),
    ('it_services','business_self_employment','mixed_basket','spend',false,false,false,'none'),
    ('jewellery','clothing_personal_care','discretionary','spend',false,false,false,'none'),
    ('kitchen','home_garden','mixed_basket','spend',false,false,false,'none'),
    ('laundry','home_garden','essential','spend',false,false,false,'none'),
    ('legal_services','business_self_employment','mixed_basket','spend',false,false,false,'none'),
    ('lighting','home_garden','mixed_basket','spend',false,false,false,'none'),
    ('live_music','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('loan_disbursement','credit_loan_repayments','not_applicable','debt_disbursement',true,false,false,'none'),
    ('loan_repayment_dd','credit_loan_repayments','essential','debt_repayment',true,false,false,'none'),
    ('loan_repayment_manual','credit_loan_repayments','essential','debt_repayment',true,false,false,'none'),
    ('loan_repayment_other','credit_loan_repayments','essential','debt_repayment',true,false,false,'none'),
    ('luggage_travel_goods','travel_holidays','discretionary','spend',false,false,false,'none'),
    ('magazines','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('marketplace_amazon','general_retail_marketplaces','mixed_basket','spend',false,false,false,'none'),
    ('marketplace_general','general_retail_marketplaces','mixed_basket','spend',false,false,false,'none'),
    ('marketplace_refurbished','general_retail_marketplaces','mixed_basket','spend',false,false,false,'none'),
    ('medicine','health_medical','essential','spend',false,false,false,'none'),
    ('memberships','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('mental_health_services','health_medical','essential','spend',false,false,false,'none'),
    ('mobile_handset','general_retail_marketplaces','mixed_basket','spend',false,false,false,'none'),
    ('mobile_phone_contract','utilities_household_bills','essential','spend',false,false,false,'none'),
    ('money_management_service','high_cost_distress_credit','discretionary','spend',false,false,false,'distress_signal'),
    ('money_transfer_fee','fees_charges','not_applicable','fee_or_penalty',false,false,false,'none'),
    ('money_transfer_service','transfers','not_applicable','p2p_transfer',false,false,false,'none'),
    ('mortgage','housing','essential','debt_repayment',true,true,false,'none'),
    ('music_other','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('musical_instruments','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('newspapers','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('night_club','eating_drinking_out','discretionary','spend',false,false,true,'none'),
    ('office_equipment','business_self_employment','mixed_basket','spend',false,false,false,'none'),
    ('office_supplies','business_self_employment','mixed_basket','spend',false,false,false,'none'),
    ('online_dating','digital_subscriptions_services','discretionary','spend',false,false,true,'none'),
    ('online_services','digital_subscriptions_services','discretionary','spend',false,false,false,'none'),
    ('optician','health_medical','essential','spend',false,false,false,'none'),
    ('overdraft_arranged','fees_charges','not_applicable','fee_or_penalty',true,false,false,'none'),
    ('overdraft_unarranged','high_cost_distress_credit','not_applicable','fee_or_penalty',false,false,false,'distress_fee'),
    ('pawnbroker','high_cost_distress_credit','essential','debt_repayment',true,false,false,'high_cost_credit'),
    ('payday_loan','high_cost_distress_credit','essential','debt_repayment',true,false,false,'high_cost_credit'),
    ('payment_intermediary','general_retail_marketplaces','mixed_basket','spend',false,false,false,'none'),
    ('pension_contribution','savings_investments','not_applicable','transfer_own_accounts',false,false,false,'none'),
    ('pension_received','income_other','not_applicable','income',false,false,false,'none'),
    ('personal_loan_repayment','credit_loan_repayments','essential','debt_repayment',true,false,false,'none'),
    ('pet_other','pets','discretionary','spend',false,false,false,'none'),
    ('pet_supplies','pets','discretionary','spend',false,false,false,'none'),
    ('pharmacy','health_medical','essential','spend',false,false,false,'none'),
    ('photography_services','business_self_employment','mixed_basket','spend',false,false,false,'none'),
    ('physical_media','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('political_donation','charitable_political_giving','discretionary','spend',false,false,false,'none'),
    ('prepaid_card','transfers','not_applicable','transfer_own_accounts',false,false,false,'none'),
    ('printing_services','business_self_employment','mixed_basket','spend',false,false,false,'none'),
    ('printing_supplies','general_retail_marketplaces','mixed_basket','spend',false,false,false,'none'),
    ('private_members_club','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('prize_competitions','gambling','discretionary','spend',false,false,true,'low_stakes_gambling'),
    ('property_management','housing','essential','spend',false,true,false,'none'),
    ('pub_bar','eating_drinking_out','discretionary','spend',false,false,true,'none'),
    ('public_transport_rail_coach','transport_motoring','essential','spend',false,false,false,'none'),
    ('refund_received','income_other','not_applicable','income',false,false,false,'none'),
    ('rent','housing','essential','spend',false,true,false,'none'),
    ('restaurant_cafe','eating_drinking_out','discretionary','spend',false,false,false,'none'),
    ('retail_finance_repayment','credit_loan_repayments','essential','debt_repayment',true,false,false,'none'),
    ('retail_other','general_retail_marketplaces','mixed_basket','spend',false,false,false,'none'),
    ('retail_small_independent','general_retail_marketplaces','mixed_basket','spend',false,false,false,'none'),
    ('retail_tv_online_shopping','general_retail_marketplaces','mixed_basket','spend',false,false,false,'none'),
    ('returned_payment','fees_charges','not_applicable','fee_or_penalty',false,false,false,'distress_fee'),
    ('revolving_credit_repayment','credit_loan_repayments','essential','debt_repayment',true,false,false,'none'),
    ('road_tax','transport_motoring','essential','spend',false,false,false,'none'),
    ('salary','income_employment','not_applicable','income',false,false,false,'none'),
    ('salary_gig','income_employment','not_applicable','income',false,false,false,'none'),
    ('savings_interest_received','income_other','not_applicable','income',false,false,false,'none'),
    ('savings_transfer','savings_investments','not_applicable','transfer_own_accounts',false,false,false,'none'),
    ('school_fees','childcare_education','essential','spend',false,false,false,'none'),
    ('services_unspecified','unclassified','mixed_basket','spend',false,false,false,'none'),
    ('skin_hair_care','clothing_personal_care','discretionary','spend',false,false,false,'none'),
    ('social_reporting','digital_subscriptions_services','discretionary','spend',false,false,false,'none'),
    ('software','digital_subscriptions_services','discretionary','spend',false,false,false,'none'),
    ('spares_repairs','transport_motoring','essential','spend',false,false,false,'none'),
    ('sports_equipment','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('sports_participation','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('sports_tickets','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('sportswear','clothing_personal_care','discretionary','spend',false,false,false,'none'),
    ('stationery','general_retail_marketplaces','mixed_basket','spend',false,false,false,'none'),
    ('storage','housing','discretionary','spend',false,false,false,'none'),
    ('streaming','digital_subscriptions_services','discretionary','spend',false,false,false,'none'),
    ('student_loan_repayment','credit_loan_repayments','essential','debt_repayment',true,false,false,'none'),
    ('supplements','health_medical','discretionary','spend',false,false,false,'none'),
    ('takeaway','eating_drinking_out','discretionary','spend',false,false,false,'none'),
    ('tax_payment','council_tax_government','essential','spend',false,true,false,'none'),
    ('tax_refund','income_other','not_applicable','income',false,false,false,'none'),
    ('taxi_rideshare','transport_motoring','mixed_basket','spend',false,false,false,'none'),
    ('theatre','entertainment_leisure','discretionary','spend',false,false,false,'none'),
    ('tobacco','groceries_household_essentials','discretionary','spend',false,false,true,'none'),
    ('tolls','transport_motoring','essential','spend',false,false,false,'none'),
    ('tools','home_garden','mixed_basket','spend',false,false,false,'none'),
    ('toys','general_retail_marketplaces','discretionary','spend',false,false,false,'none'),
    ('trade_union','business_self_employment','mixed_basket','spend',false,false,false,'none'),
    ('tradesmen','home_garden','essential','spend',false,false,false,'none'),
    ('transfer_bank_unspecified','transfers','not_applicable','transfer_own_accounts',false,false,false,'none'),
    ('transfer_international','transfers','not_applicable','p2p_transfer',false,false,false,'none'),
    ('transfer_mobile_app','transfers','not_applicable','p2p_transfer',false,false,false,'none'),
    ('transfer_own_account','transfers','not_applicable','transfer_own_accounts',false,false,false,'none'),
    ('transfer_p2p','transfers','not_applicable','p2p_transfer',false,false,false,'none'),
    ('transport_other','transport_motoring','essential','spend',false,false,false,'none'),
    ('travel_other','travel_holidays','discretionary','spend',false,false,false,'none'),
    ('tv_licence','utilities_household_bills','essential','spend',false,true,false,'none'),
    ('unclassified_card_spend','unclassified','mixed_basket','spend',false,false,false,'none'),
    ('unclassified_other','unclassified','mixed_basket','spend',false,false,false,'none'),
    ('unclassified_recurring','unclassified','mixed_basket','spend',false,false,false,'none'),
    ('unclassified_transfer','unclassified','mixed_basket','spend',false,false,false,'none'),
    ('utility_other','utilities_household_bills','essential','spend',false,true,false,'none'),
    ('vaping','groceries_household_essentials','discretionary','spend',false,false,true,'none'),
    ('vehicle_maintenance','transport_motoring','essential','spend',false,false,false,'none'),
    ('vehicle_mot','transport_motoring','essential','spend',false,false,false,'none'),
    ('vehicle_purchase','transport_motoring','mixed_basket','spend',false,false,false,'none'),
    ('vehicle_servicing','transport_motoring','essential','spend',false,false,false,'none'),
    ('veterinary','pets','essential','spend',false,false,false,'none'),
    ('vouchers','general_retail_marketplaces','mixed_basket','spend',false,false,false,'none'),
    ('waste_services','utilities_household_bills','essential','spend',false,false,false,'none'),
    ('water','utilities_household_bills','essential','spend',false,true,false,'none'),
    ('wealth_management','savings_investments','not_applicable','transfer_own_accounts',false,false,false,'none'),
    ('web_services','digital_subscriptions_services','discretionary','spend',false,false,false,'none'),
    ('weight_loss','health_medical','discretionary','spend',false,false,false,'none')
])),

-- ---------- EQUIFAX ----------
eqx_raw AS (
  SELECT
    PrimaryCategoryDescription AS pri,
    SubCategoryDescription AS sub,
    VendorDescription AS vendor,
    Description AS description_raw,
    IF(TransactionTypeId=1,'credit','debit') AS direction,
    Amount
  FROM `raylo-production.equifax_data.open_banking_full_dump`
  TABLESAMPLE SYSTEM (2 PERCENT)
),
eqx_resolved AS (
  SELECT r.*,
    CASE
      -- T1: direction-dependent overrides
      WHEN r.pri LIKE 'Gambling and Betting%' AND r.direction='credit' THEN 'gambling_unspecified'
      WHEN r.sub='Council' AND r.direction='credit' THEN 'salary'
      -- T2: compound rule - gig income
      WHEN r.pri='Identified Salary' AND r.sub IN ('Taxis','Delivery','Take Away') THEN 'salary_gig'
      WHEN r.pri='Identified Salary' AND r.sub IN ('Recruitment Services','Employment Agencies') THEN 'income_agency_work'
      -- T2: provider-entity collisions (Tesco Bank/Petrol/PhoneIns; HMRC
      -- Child Benefit / tax credits / SA refunds). Must precede T4.
      WHEN LOWER(TRIM(r.vendor))='tesco' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\btesco bank\b') THEN 'financial_institution_unspecified'
      WHEN LOWER(TRIM(r.vendor))='tesco' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'tescophoneins') THEN 'insurance_other'
      WHEN LOWER(TRIM(r.vendor))='tesco' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'caf[eé]') THEN 'restaurant_cafe'
      WHEN LOWER(TRIM(r.vendor)) IN ('tesco', 'one stop', 'post office', 'u.s. post office', 'asda', 'sainsbury\'s', 'co-op') AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\batm\b|\blnk\b|cash\s+at\b|cash\s+withdrawal') THEN 'cash_withdrawal'
      WHEN LOWER(TRIM(r.vendor)) IN ('tesco', 'one stop', 'post office', 'u.s. post office', 'asda', 'sainsbury\'s', 'co-op') AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\batm\b|cash\s+deposit') THEN 'cash_deposit'
      WHEN LOWER(TRIM(r.vendor))='tesco' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'petrol|\bpfs\b|\bfuel\b') THEN 'fuel'
      WHEN LOWER(TRIM(r.vendor)) IN ('morr', 'cd morr') AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'caf[eé]') THEN 'restaurant_cafe'
      WHEN LOWER(TRIM(r.vendor)) IN ('co-op', 'sainsbury\'s', 'asda', 'morr', 'cd morr') AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'petrol|\bpfs\b|\bfuel\b') THEN 'fuel'
      WHEN LOWER(TRIM(r.vendor)) IN ('hmrc', 'hm revenue and customs') AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'child\s+benefits?') THEN 'benefits_state'
      WHEN LOWER(TRIM(r.vendor)) IN ('hmrc', 'hm revenue and customs') AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'work(?:ing)?\s+and\s+child\s+(?:tax\s+)?credits?|work(?:ing)?\s+and\s+child\s+tc\b|child\s+tax\s+credits?|working\s+tax\s+credits?') THEN 'benefits_state'
      WHEN LOWER(TRIM(r.vendor)) IN ('hmrc', 'hm revenue and customs') AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\bhmrc\s+sa\b|\bgov\.uk\s+sa\b|\bself[\s-]*assess') THEN 'tax_refund'
      WHEN r.direction='debit' AND (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), r'\bkfc\b') OR REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\bkfc\b')) THEN 'takeaway'
      WHEN LOWER(TRIM(r.vendor))='tiktok' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'tiktok\s*shop|\bshop\s*seller') THEN 'marketplace_general'
      WHEN LOWER(TRIM(r.vendor))='tiktok' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'shop\s*seller') THEN 'income_other_unspecified'
      WHEN LOWER(TRIM(r.vendor))='sky' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sky\s*protect|\bdgi\b.*protect|protect.*\bdgi\b') THEN 'insurance_other'
      WHEN LOWER(TRIM(r.vendor))='child benefits' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'dwp\s*cms|dwpcms|cmsgb2012|child\s+maintenance') THEN 'income_other_unspecified'
      WHEN LOWER(TRIM(r.vendor))='asda' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'asda\s*mobile') THEN 'mobile_phone_contract'
      WHEN LOWER(TRIM(r.vendor))='asda' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'asda\s*living') THEN 'home_accessories'
      WHEN LOWER(TRIM(r.vendor))='vodafone' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'device') THEN 'mobile_handset'
      WHEN LOWER(TRIM(r.vendor))='amazon' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'prime\s*video') THEN 'streaming'
      WHEN LOWER(TRIM(r.vendor))='bolt' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'stackblitz') THEN 'software'
      WHEN LOWER(TRIM(r.vendor))='haven holidays' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'richard\s+haven') THEN 'beauty_treatment'
      WHEN LOWER(TRIM(r.vendor))='apple store' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'ingle\s+store') THEN 'convenience_store'
      WHEN r.direction='credit' AND (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), r'amazon\s+uk\s+services') OR REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'amazon\s+uk\s+services')) THEN 'salary'
      WHEN LOWER(TRIM(r.vendor))='grosvenor casino' AND r.direction='credit' AND NOT REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'returned|refund(ed)?|reversal of') THEN 'salary'
      WHEN LOWER(TRIM(r.vendor))='admiral' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'casino') THEN 'gambling_casino'
      WHEN LOWER(TRIM(r.vendor))='places for people' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'leisure|nyx|\\bleis\\b') THEN 'gym_fitness'
      WHEN LOWER(TRIM(r.vendor))='nuffield health' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'hospital|clinic|infirmar') THEN 'hospital'
      WHEN LOWER(TRIM(r.vendor))='ocado' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'central\\s+serv|ocado\\s+central') THEN 'salary'
      WHEN LOWER(TRIM(r.vendor))='sodexo' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'healthcare|salary|payroll|wages') THEN 'salary'
      WHEN LOWER(TRIM(r.vendor))='ask italian' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'azzurri|salary|payroll|wages|\\bbgc\\b') THEN 'salary'
      WHEN LOWER(TRIM(r.vendor))='fife council' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'bgc|salary|payroll|wages|faster\\s+payment|\\bfps\\b') THEN 'salary'
      WHEN LOWER(TRIM(r.vendor))='plum fintech' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'modulo') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.vendor))='avon' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'[a-z]{3,}\\s+[a-z]{3,}') THEN 'income_other_unspecified'
      WHEN LOWER(TRIM(r.vendor))='prudential' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'annuity|pension|payout|\\bbgc\\b') THEN 'pension_received'
      WHEN LOWER(TRIM(r.vendor))='fluid' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'fluid\\s+focus|\\bto\\s+[a-z]+\\s+[a-z]+') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.vendor))='now' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\bentertai\\b') THEN 'streaming'
      WHEN LOWER(TRIM(r.vendor))='now' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'paypal') THEN 'streaming'
      WHEN LOWER(TRIM(r.vendor))='paypal' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\*now\\b') THEN 'streaming'
      WHEN LOWER(TRIM(r.vendor))='paypal' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'payin\\s*3|pay\\s*in\\s*[34]|\\bpayin3\\b|pypl\\s*payin') THEN 'bnpl'
      WHEN LOWER(TRIM(r.vendor))='paypal credit' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'payin\\s*3|pay\\s*in\\s*[34]|\\bpayin3\\b|pypl\\s*payin') THEN 'bnpl'
      WHEN LOWER(TRIM(r.vendor))='paypal' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\*paypal\\s*cre|\\bpaypal\\s*credit\\b') THEN 'revolving_credit_repayment'
      WHEN LOWER(TRIM(r.vendor))='white lion' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\bhotel\\b') THEN 'accommodation'
      WHEN LOWER(TRIM(r.vendor))='cts' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'napa|auto\\s+parts|spares') THEN 'spares_repairs'
      WHEN LOWER(TRIM(r.vendor))='transferwise' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'via\\s+mobile') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.vendor))='mercedes-benz' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'mbfin|financial') THEN 'car_finance_repayment'
      WHEN LOWER(TRIM(r.vendor))='mercedes-benz' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\bof\\s+') THEN 'salary'
      WHEN LOWER(TRIM(r.vendor))='mercedes-benz' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\bof\\s+|servic|\\bmot\\b') THEN 'vehicle_servicing'
      WHEN LOWER(TRIM(r.vendor))='the kingfisher' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'convenience|grocer|\\bstore\\b') THEN 'convenience_store'
      WHEN LOWER(TRIM(r.vendor))='gem' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'gem1|\\bcasino\\b') THEN 'gambling_casino'
      WHEN LOWER(TRIM(r.vendor))='gem' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'via\\s+mobile') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.vendor))='cotswold outdoor' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\d{6,}|salary|payroll|wages') THEN 'salary'
      WHEN LOWER(TRIM(r.vendor))='wood j' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'hsm|\\bholiday\\b') THEN 'holiday_package'
      WHEN LOWER(TRIM(r.vendor))='council' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'council\\s+tax') THEN 'council_tax'
      WHEN LOWER(TRIM(r.vendor))='city' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'city\\s+airport|london\\s+city') THEN 'airport_spend'
      WHEN LOWER(TRIM(r.vendor))='city' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'city\\s+council') THEN 'government_services'
      WHEN LOWER(TRIM(r.vendor))='home' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'etsy\\.com|homemadebouti') THEN 'gifts_flowers'
      WHEN LOWER(TRIM(r.vendor))='home' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'247\\s+home\\s+rescue|home\\s+rescue') THEN 'home_repair'
      WHEN LOWER(TRIM(r.vendor))='home' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'online\\s+home\\s+shop') THEN 'home_accessories'
      WHEN LOWER(TRIM(r.vendor))='home' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'home\\s+glasgow|\\bglasgow\\b') THEN 'mortgage'
      WHEN LOWER(TRIM(r.vendor))='orbit' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'credit\\s+services') THEN 'debt_collection'
      WHEN LOWER(TRIM(r.vendor))='orbit' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'allpay|south\\s+ho|housing|\\brent\\b') THEN 'rent'
      WHEN LOWER(TRIM(r.vendor))='plus' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'plus500') THEN 'investment_trading'
      WHEN LOWER(TRIM(r.vendor))='plus' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'direct\\s+debit\\s+plus|plus\\s*finance|plus\\s*loan') THEN 'personal_loan_repayment'
      WHEN LOWER(TRIM(r.vendor))='liberty' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\bgas\\b|electric|energy') THEN 'energy'
      WHEN LOWER(TRIM(r.vendor))='virgin mobile' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'virgin\\s+money') THEN 'credit_card_repayment'
      WHEN LOWER(TRIM(r.vendor))='the grove' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'welwyn|chandler') THEN 'accommodation'
      WHEN LOWER(TRIM(r.vendor))='cd glasgow' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sheriff\s+court') THEN 'government_services'
      WHEN LOWER(TRIM(r.vendor))='cd glasgow' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'glasgow\s+central') THEN 'public_transport_rail_coach'
      WHEN LOWER(TRIM(r.vendor))='cd glasgow' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'qst\s+stn') THEN 'public_transport_rail_coach'
      WHEN LOWER(TRIM(r.vendor))='cd shop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'schiphol|let\'?s\s+play') THEN 'airport_spend'
      WHEN LOWER(TRIM(r.vendor))='cd shop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'khanz') THEN 'convenience_store'
      WHEN LOWER(TRIM(r.vendor))='cd shop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'shop\s+reading') THEN 'retail_other'
      WHEN LOWER(TRIM(r.vendor))='foot' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'firstfootsoldiers') THEN 'entertainment_other'
      WHEN LOWER(TRIM(r.vendor))='foot' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'stoke\s+city\s+footbal') THEN 'sports_tickets'
      WHEN LOWER(TRIM(r.vendor))='glossop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'valley\s+cids') THEN 'charitable_donation'
      WHEN LOWER(TRIM(r.vendor))='glossop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'district\s*gol') THEN 'sports_participation'
      WHEN LOWER(TRIM(r.vendor))='glossop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'glossop\s+sub|sumup\s*\*?\s*glossop\s+sub') THEN 'takeaway'
      WHEN LOWER(TRIM(r.vendor))='crawley' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'crawley\.gov') THEN 'government_services'
      WHEN LOWER(TRIM(r.vendor))='crawley' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'black\s+belt') THEN 'sports_participation'
      WHEN LOWER(TRIM(r.vendor))='track' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'on\s+track|southern\s+ra') THEN 'public_transport_rail_coach'
      WHEN LOWER(TRIM(r.vendor))='track' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'track\s+bandits') THEN 'clothing_general'
      WHEN LOWER(TRIM(r.vendor))='longton' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'service\s+station') THEN 'fuel'
      WHEN LOWER(TRIM(r.vendor))='longton' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'hall\s+farm') THEN 'car_parking'
      WHEN LOWER(TRIM(r.vendor))='cd stirling' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'costa') THEN 'restaurant_cafe'
      WHEN LOWER(TRIM(r.vendor))='cd stirling' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'goosecroft') THEN 'car_parking'
      WHEN LOWER(TRIM(r.vendor))='cd stirling' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'stirling\s+council|-ips|\bips\b') THEN 'car_parking'
      WHEN LOWER(TRIM(r.vendor))='royal victoria' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'infirma') THEN 'hospital'
      WHEN LOWER(TRIM(r.vendor))='royal victoria' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'country') THEN 'days_out'
      WHEN LOWER(TRIM(r.vendor))='cd merlin' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'cinemas?') THEN 'cinema'
      WHEN LOWER(TRIM(r.vendor))='cd merlin' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'attractions?') THEN 'days_out'
      WHEN LOWER(TRIM(r.vendor))='cd merlin' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\bderby\b') THEN 'entertainment_other'
      WHEN LOWER(TRIM(r.vendor))='cd colchester' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'leisure') THEN 'sports_participation'
      WHEN LOWER(TRIM(r.vendor))='cd colchester' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'borough|-ips|\bips\b') THEN 'car_parking'
      WHEN LOWER(TRIM(r.vendor))='cd apex' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'kart') THEN 'days_out'
      WHEN LOWER(TRIM(r.vendor))='cd apex' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'harlow') THEN 'business_services'
      WHEN LOWER(TRIM(r.vendor))='cd con' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'coningham') THEN 'pub_bar'
      WHEN LOWER(TRIM(r.vendor))='cd con' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'conniburrow') THEN 'unclassified_card_spend'
      WHEN LOWER(TRIM(r.vendor))='cd miss' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'whippy') THEN 'takeaway'
      WHEN LOWER(TRIM(r.vendor))='cd miss' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'glam|aesthetics') THEN 'beauty_treatment'
      WHEN LOWER(TRIM(r.vendor))='medical' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'medical\s+aid') THEN 'charitable_donation'
      WHEN LOWER(TRIM(r.vendor))='medical' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'bill\s+medical') THEN 'health_other'
      WHEN LOWER(TRIM(r.vendor))='medical' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'medical-?supermarket') THEN 'pharmacy'
      WHEN LOWER(TRIM(r.vendor))='wardrobe' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'witch') THEN 'pub_bar'
      WHEN LOWER(TRIM(r.vendor))='wardrobe' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'earth\s+wardrobe') THEN 'clothing_general'
      WHEN LOWER(TRIM(r.vendor))='wardrobe' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\bwardrobe\b') THEN 'clothing_general'
      WHEN LOWER(TRIM(r.vendor))='cd fresh' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'garbage') THEN 'clothing_general'
      WHEN LOWER(TRIM(r.vendor))='cd fresh' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'fresh\s+metro') THEN 'groceries'
      WHEN LOWER(TRIM(r.vendor))='c k' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'knutsford') THEN 'restaurant_cafe'
      WHEN LOWER(TRIM(r.vendor))='c k' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'kremlin') THEN 'pub_bar'
      WHEN LOWER(TRIM(r.vendor))='botany' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'kiosk') THEN 'takeaway'
      WHEN LOWER(TRIM(r.vendor))='botany' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'inn') THEN 'pub_bar'
      WHEN LOWER(TRIM(r.vendor))='afc wigan wallgate' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'northern\s+trains') THEN 'public_transport_rail_coach'
      WHEN LOWER(TRIM(r.vendor))='afc wigan wallgate' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'wallgate|afc\s+wigan') THEN 'takeaway'
      WHEN LOWER(TRIM(r.vendor))='scan' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'scan\.com') THEN 'health_other'
      WHEN LOWER(TRIM(r.vendor))='scan' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'scandiscents') THEN 'home_accessories'
      WHEN LOWER(TRIM(r.vendor))='mablethorpe' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'grange\s+leisure') THEN 'accommodation'
      WHEN LOWER(TRIM(r.vendor))='mablethorpe' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\brock\b') THEN 'confectionary'
      WHEN LOWER(TRIM(r.vendor))='wigmore' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'pharmacy') THEN 'pharmacy'
      WHEN LOWER(TRIM(r.vendor))='wigmore' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'ppoint|wigmore\s+&\s+ham|gillingham') THEN 'convenience_store'
      WHEN LOWER(TRIM(r.vendor))='cd alder' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'vets?') THEN 'veterinary'
      WHEN LOWER(TRIM(r.vendor))='cd alder' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'aldermaston') THEN 'fuel'
      WHEN LOWER(TRIM(r.vendor))='cd drum' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'filling\s+station') THEN 'fuel'
      WHEN LOWER(TRIM(r.vendor))='cd drum' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'drum\s+central') THEN 'musical_instruments'
      WHEN LOWER(TRIM(r.vendor))='c unique' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'petrol') THEN 'fuel'
      WHEN LOWER(TRIM(r.vendor))='c unique' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'unique\s+mobile|\bmobile\b') THEN 'mobile_handset'
      WHEN LOWER(TRIM(r.vendor))='mexpress uk cd' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'medexpress|med\s*express') THEN 'pharmacy'
      WHEN LOWER(TRIM(r.vendor))='mexpress uk cd' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'molina') THEN 'delivery_courier'
      WHEN LOWER(TRIM(r.vendor))='melanie and paul heweston' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'insurance') THEN 'insurance_general'
      WHEN LOWER(TRIM(r.vendor))='melanie and paul heweston' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\bloan\b') THEN 'loan_repayment_manual'
      WHEN LOWER(TRIM(r.vendor))='wik' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'maciagowska|repayment') THEN 'loan_repayment_manual'
      WHEN LOWER(TRIM(r.vendor))='wik' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sopel') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.vendor))='artbox' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'scoop') THEN 'restaurant_cafe'
      WHEN LOWER(TRIM(r.vendor))='artbox' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'artbox') THEN 'stationery'
      WHEN LOWER(TRIM(r.vendor))='cd best' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'best4vapes|best\s*4\s*vapes') THEN 'vaping'
      WHEN LOWER(TRIM(r.vendor))='cd best' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'best\s+one') THEN 'convenience_store'
      WHEN LOWER(TRIM(r.vendor))='fitzsimons' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'joshua') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.vendor))='fitzsimons' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'fitzsimons') THEN 'pub_bar'
      WHEN LOWER(TRIM(r.vendor))='banquet' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'paypal') THEN 'music_other'
      WHEN LOWER(TRIM(r.vendor))='banquet' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sq\s*\*|nottingham') THEN 'restaurant_cafe'
      WHEN LOWER(TRIM(r.vendor))='thurrock' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'community') THEN 'government_services'
      WHEN LOWER(TRIM(r.vendor))='thurrock' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'borough|-ips') THEN 'car_parking'
      WHEN LOWER(TRIM(r.vendor))='derek' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'wright|loan\s+repayment') THEN 'loan_repayment_manual'
      WHEN LOWER(TRIM(r.vendor))='derek' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'derek\s+jones|\bjones\b') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.vendor))='the black' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'black\s+country') THEN 'takeaway'
      WHEN LOWER(TRIM(r.vendor))='the black' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'blackheath') THEN 'pub_bar'
      WHEN LOWER(TRIM(r.vendor))='east bridgford' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'gdn|garden') THEN 'garden'
      WHEN LOWER(TRIM(r.vendor))='east bridgford' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'medica') THEN 'health_other'
      WHEN LOWER(TRIM(r.vendor))='cd tp' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'amity|kebabs?') THEN 'takeaway'
      WHEN LOWER(TRIM(r.vendor))='cd tp' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'b\s+and\s+j') THEN 'convenience_store'
      WHEN LOWER(TRIM(r.vendor))='cd no.' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'off\s+licence') THEN 'alcohol_beer_spirits'
      WHEN LOWER(TRIM(r.vendor))='cd no.' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'no\.?\s*7\s+restaurant|restaurant') THEN 'restaurant_cafe'
      WHEN LOWER(TRIM(r.vendor))='cd sheffield' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'chaucer') THEN 'convenience_store'
      WHEN LOWER(TRIM(r.vendor))='cd sheffield' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'meadow') THEN 'retail_other'
      WHEN LOWER(TRIM(r.vendor))='cd green' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'green\s+man') THEN 'pub_bar'
      WHEN LOWER(TRIM(r.vendor))='cd green' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'green\s+valley') THEN 'groceries'
      WHEN LOWER(TRIM(r.vendor))='egg' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'zettle|eggbugland') THEN 'retail_other'
      WHEN LOWER(TRIM(r.vendor))='egg' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'162224|direct\s+debit|\begg\b') THEN 'energy'
      WHEN LOWER(TRIM(r.vendor))='jasmine' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'restaurant') THEN 'restaurant_cafe'
      WHEN LOWER(TRIM(r.vendor))='jasmine' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'chesney|sortcode|\d{10,}') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.vendor))='paymy.vet' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'groom') THEN 'pet_other'
      WHEN LOWER(TRIM(r.vendor))='paymy.vet' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'vets?|bolton') THEN 'veterinary'
      WHEN LOWER(TRIM(r.vendor))='bill\'s' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'nanny') THEN 'takeaway'
      WHEN LOWER(TRIM(r.vendor))='bill\'s' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'mcgill|buses') THEN 'public_transport_rail_coach'
      WHEN LOWER(TRIM(r.vendor))='bill\'s' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'restaurant') THEN 'restaurant_cafe'
      WHEN LOWER(TRIM(r.vendor))='reddish' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'service\s+stati') THEN 'fuel'
      WHEN LOWER(TRIM(r.vendor))='reddish' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'convenience') THEN 'convenience_store'
      WHEN LOWER(TRIM(r.vendor))='hafod' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sq\s*\*') THEN 'restaurant_cafe'
      WHEN LOWER(TRIM(r.vendor))='hafod' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'housing') THEN 'rent'
      WHEN LOWER(TRIM(r.vendor))='hart' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'hart\s+il|sortcode') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.vendor))='hart' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'district\s+council|\bcouncil\b') THEN 'council_tax'
      WHEN LOWER(TRIM(r.vendor))='blackwell\'s' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sammy|k\s+a\s+blackwell') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.vendor))='blackwell\'s' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'blackwell') THEN 'books'
      WHEN LOWER(TRIM(r.vendor))='gamesys operation' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'gamesys') THEN 'gambling_unspecified'
      WHEN LOWER(TRIM(r.vendor))='the ups store' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'ppoint|g\s+and\s+s\s+stores') THEN 'convenience_store'
      WHEN LOWER(TRIM(r.vendor))='the ups store' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'ups\s+store') THEN 'delivery_courier'
      WHEN LOWER(TRIM(r.vendor))='hiba' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'bibs|bakri|clothing') THEN 'clothing_general'
      WHEN LOWER(TRIM(r.vendor))='hiba' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sagheer') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.vendor))='collection pot' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'collection\s+pot') THEN 'restaurant_cafe'
      WHEN LOWER(TRIM(r.vendor))='wirral mbc' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\batp\b') THEN 'car_parking'
      WHEN LOWER(TRIM(r.vendor))='wirral mbc' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'wirral\s+mbc') THEN 'council_tax'
      WHEN LOWER(TRIM(r.vendor))='barbican' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'news') THEN 'convenience_store'
      WHEN LOWER(TRIM(r.vendor))='barbican' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'barbican') THEN 'theatre'
      WHEN LOWER(TRIM(r.vendor))='wine lodge' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'ppoint') THEN 'alcohol_beer_spirits'
      WHEN LOWER(TRIM(r.vendor))='wine lodge' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'wine\s+lodge') THEN 'pub_bar'
      WHEN LOWER(TRIM(r.vendor))='pier' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'fish|chips') THEN 'takeaway'
      WHEN LOWER(TRIM(r.vendor))='pier' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'pieralongia') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.vendor))='pier' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'pier\s+36|donaghadee') THEN 'pub_bar'
      WHEN LOWER(TRIM(r.vendor))='amber valley borough council' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'-ips|\bips\b') THEN 'car_parking'
      WHEN LOWER(TRIM(r.vendor))='roadchef' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'whsmi') THEN 'convenience_store'
      WHEN LOWER(TRIM(r.vendor))='wembley park' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'expre') THEN 'convenience_store'
      WHEN LOWER(TRIM(r.vendor))='rbs-natwest w/end credit' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'recollection|monzo') THEN 'financial_services_other'
      -- T3: MECHANISM-OVERRIDE primaries (mechanism determines leaf regardless of merchant)
      WHEN r.pri='Identified Salary' THEN 'salary'
      WHEN r.pri='Refund' THEN 'refund_received'
      WHEN r.pri IN ('Benefits','Welfare') THEN 'benefits_state'
      WHEN r.pri='Pension Payout' THEN 'pension_received'
      WHEN r.pri='Tax Refund' THEN 'tax_refund'
      WHEN r.pri='Cash Back' THEN 'cashback'
      WHEN r.pri='Cash Machine' THEN 'cash_withdrawal'
      WHEN r.pri='Cash Deposit' THEN 'cash_deposit'
      WHEN r.pri IN ('Interest','Interests and Dividends') THEN 'savings_interest_received'
      WHEN r.pri='Balance Transfers' THEN 'balance_transfer'
      WHEN r.pri='Adjustments' THEN 'adjustment'
      -- T1 (dict-informed): bookmaker credits stay unspecified even when T4
      -- would assign a debit subtype. Plaid native T1 only sees Plaid's
      -- gambling category, so salary-mislabeled Sky Bet credits used to lose to T4.
      WHEN r.direction='credit' AND d.leaf IN ('gambling_betting', 'gambling_casino', 'gambling_bingo', 'gambling_lottery') THEN 'gambling_unspecified'
      WHEN r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\brefund(ed)?\b') AND (d.leaf IS NULL OR d.leaf NOT IN ('gambling_betting', 'gambling_casino', 'gambling_bingo', 'gambling_lottery')) THEN 'refund_received'
      WHEN r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'returned\s+(direct\s+debit|standing\s+order)|direct\s+debit\s+reversal|\breversal of\b') THEN 'returned_payment'
      WHEN LOWER(TRIM(r.vendor))='youlend' AND r.direction='credit' THEN 'loan_disbursement'
      -- T4: merchant dictionary (provider-independent, overrides both providers' own categories)
      WHEN d.leaf IS NOT NULL THEN d.leaf
      -- T5: deterministic rules
      WHEN REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '^(mr|mrs|miss|ms|dr)\\s+') THEN 'transfer_p2p'
      WHEN REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '^[a-z]\\s+[a-z]{2,}$') THEN 'transfer_p2p'
      WHEN REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), CONCAT(r'\b(', 'mum|dad|mom|nan|nana|gran|granny|grandad|sister|brother|son|daughter|wife|husband', r')\b')) THEN 'transfer_p2p'
      WHEN REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '^exchanged to (btc|eth|sol|xrp|ada|doge)') THEN 'crypto'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '(petrol|fuel)\\s*(station)?$') AND r.direction = 'debit') THEN 'fuel'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '(bingo|casino)') AND r.direction = 'debit') THEN 'gambling_unspecified'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '\\b(bet|betting|bookmaker)\\b|\\bbet\\s?\\d\\d+\\b|\\b(sky|uni|coral|lad|net|virgin|paddy|smark)bet\\b|\\bbet(fred|fair|victor|way|uk|bright)\\b') AND r.direction = 'debit') THEN 'gambling_betting'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '\\b(lottery|lotto)\\b') AND r.direction = 'debit') THEN 'gambling_lottery'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '\\b(debt (collection|recovery)|collections? ltd)\\b') AND r.direction = 'debit') THEN 'debt_collection'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), CONCAT(r'\b(', 'child maintenance', r')\b')) AND r.direction = 'credit') THEN 'income_other_unspecified'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), CONCAT(r'\b(', 'we buy any car', r')\b')) AND r.direction = 'credit') THEN 'income_other_unspecified'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), CONCAT(r'\b(', 'we buy any car', r')\b')) AND r.direction = 'debit') THEN 'vehicle_purchase'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '\\b(payday(?:\\s*loans?)?|wonga|quick\\s?quid|lending\\s?stream|118\\s*(?:118\\s*)?money|cashfloat|quid\\s?market|morses\\s?club|moneyboat|tick\\s?tock\\s*loans?|sunny\\s+loans?|cash\\s?asap|fast\\s+loan)\\b') AND r.direction = 'debit') THEN 'payday_loan'
      WHEN ((REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '\\bmorr\\b') AND NOT REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), 'petrol|pfs|fuel|caf[eé]')) AND r.direction = 'debit') THEN 'groceries'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '\\bwages\\b') AND r.direction = 'credit') THEN 'salary'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '\\boff\\s+licence\\b') AND r.direction = 'debit') THEN 'alcohol_beer_spirits'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '\\b(car park|parking)\\b') AND r.direction = 'debit') THEN 'car_parking'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '\\b(vets?|veterinary)\\b') AND r.direction = 'debit') THEN 'veterinary'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '\\b(pharmacy|chemist)\\b') AND r.direction = 'debit') THEN 'pharmacy'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bcouncil tax\\b') AND r.direction = 'debit') THEN 'council_tax'
      WHEN ((REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\b(rent|landlord)\\b') AND NOT REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), 'rent\\s*/\\s*buy|video rent|rent.?a.?car')) AND r.direction = 'debit') THEN 'rent'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\b(payday(?:\\s*loans?)?|wonga|quick\\s?quid|lending\\s?stream|118\\s*(?:118\\s*)?money|cashfloat|quid\\s?market|morses\\s?club|moneyboat|tick\\s?tock\\s*loans?|sunny\\s+loans?|cash\\s?asap|fast\\s+loan)\\b') AND r.direction = 'debit') THEN 'payday_loan'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bexpo international\\s+sup') AND r.direction = 'debit') THEN 'groceries_specialist'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bsheriff\\s+court\\b') AND r.direction = 'debit') THEN 'government_services'
      WHEN ((REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\b(universal\\s+credit|dwp\\s+uc\\b|dwp\\s+eesa|dwp\\s+pc\\b|pension\\s+credit|child\\s+benefits?|work(?:ing)?\\s+and\\s+child\\s+(?:tc|tax)|child\\s+tax\\s+credit|working\\s+tax\\s+credit|carers?\\s+allowance|disability\\s+living\\s+allowance|personal\\s+independence\\s+payment|employment\\s+and\\s+support\\s+allowance)\\b') AND NOT REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), 'debt|recovery|cms|maintenance|enforcement')) AND r.direction = 'credit') THEN 'benefits_state'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bscholastic\\s+book') AND r.direction = 'debit') THEN 'books'
      WHEN ((REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bwages\\b') AND NOT REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), 'minimum\\s+wage|living\\s+wage')) AND r.direction = 'credit') THEN 'salary'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bentertai\\b') AND r.direction = 'debit') THEN 'streaming'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), 'paypal\\s*\\*now') AND r.direction = 'debit') THEN 'streaming'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\boff\\s+licence\\b') AND r.direction = 'debit') THEN 'alcohol_beer_spirits'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bstep[\\s-]*change\\b') AND r.direction = 'debit') THEN 'debt_management_plan'
      WHEN ((REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bpaypal\\s*\\*?\\s*paypal\\s*cre|\\bpaypal\\s+credit\\b') AND NOT REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), 'payin\\s*3|pay\\s*in\\s*[34]|\\bpayin3\\b|pypl\\s*payin')) AND r.direction = 'debit') THEN 'revolving_credit_repayment'
      -- T6: provider crosswalk fallback (sub = WHAT, primary = mechanism fallback)
      WHEN s.leaf IS NOT NULL THEN s.leaf
      WHEN p.leaf IS NOT NULL THEN p.leaf
      ELSE 'unclassified_other'
    END AS leaf,
    CASE
      WHEN r.pri LIKE 'Gambling and Betting%' AND r.direction='credit' THEN 'T1_direction'
      WHEN r.sub='Council' AND r.direction='credit' THEN 'T1_direction'
      WHEN r.pri='Identified Salary' AND r.sub IN ('Taxis','Delivery','Take Away') THEN 'T2_compound'
      WHEN r.pri='Identified Salary' AND r.sub IN ('Recruitment Services','Employment Agencies') THEN 'T2_compound'
      WHEN LOWER(TRIM(r.vendor))='tesco' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\btesco bank\b') THEN 'T2_compound_tesco_bank'
      WHEN LOWER(TRIM(r.vendor))='tesco' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'tescophoneins') THEN 'T2_compound_tesco_phoneins'
      WHEN LOWER(TRIM(r.vendor))='tesco' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'caf[eé]') THEN 'T2_compound_tesco_cafe'
      WHEN LOWER(TRIM(r.vendor)) IN ('tesco', 'one stop', 'post office', 'u.s. post office', 'asda', 'sainsbury\'s', 'co-op') AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\batm\b|\blnk\b|cash\s+at\b|cash\s+withdrawal') THEN 'T2_compound_instore_atm'
      WHEN LOWER(TRIM(r.vendor)) IN ('tesco', 'one stop', 'post office', 'u.s. post office', 'asda', 'sainsbury\'s', 'co-op') AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\batm\b|cash\s+deposit') THEN 'T2_compound_instore_atm_deposit'
      WHEN LOWER(TRIM(r.vendor))='tesco' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'petrol|\bpfs\b|\bfuel\b') THEN 'T2_compound_tesco_petrol'
      WHEN LOWER(TRIM(r.vendor)) IN ('morr', 'cd morr') AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'caf[eé]') THEN 'T2_compound_morr_cafe'
      WHEN LOWER(TRIM(r.vendor)) IN ('co-op', 'sainsbury\'s', 'asda', 'morr', 'cd morr') AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'petrol|\bpfs\b|\bfuel\b') THEN 'T2_compound_grocer_petrol'
      WHEN LOWER(TRIM(r.vendor)) IN ('hmrc', 'hm revenue and customs') AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'child\s+benefits?') THEN 'T2_compound_hmrc_child_benefit'
      WHEN LOWER(TRIM(r.vendor)) IN ('hmrc', 'hm revenue and customs') AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'work(?:ing)?\s+and\s+child\s+(?:tax\s+)?credits?|work(?:ing)?\s+and\s+child\s+tc\b|child\s+tax\s+credits?|working\s+tax\s+credits?') THEN 'T2_compound_hmrc_tax_credit'
      WHEN LOWER(TRIM(r.vendor)) IN ('hmrc', 'hm revenue and customs') AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\bhmrc\s+sa\b|\bgov\.uk\s+sa\b|\bself[\s-]*assess') THEN 'T2_compound_hmrc_sa_refund'
      WHEN r.direction='debit' AND (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), r'\bkfc\b') OR REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\bkfc\b')) THEN 'T2_compound_kfc'
      WHEN LOWER(TRIM(r.vendor))='tiktok' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'tiktok\s*shop|\bshop\s*seller') THEN 'T2_compound_tiktok_shop'
      WHEN LOWER(TRIM(r.vendor))='tiktok' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'shop\s*seller') THEN 'T2_compound_tiktok_shop_seller'
      WHEN LOWER(TRIM(r.vendor))='sky' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sky\s*protect|\bdgi\b.*protect|protect.*\bdgi\b') THEN 'T2_compound_sky_protect'
      WHEN LOWER(TRIM(r.vendor))='child benefits' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'dwp\s*cms|dwpcms|cmsgb2012|child\s+maintenance') THEN 'T2_compound_cms_not_child_benefit'
      WHEN LOWER(TRIM(r.vendor))='asda' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'asda\s*mobile') THEN 'T2_compound_asda_mobile'
      WHEN LOWER(TRIM(r.vendor))='asda' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'asda\s*living') THEN 'T2_compound_asda_living'
      WHEN LOWER(TRIM(r.vendor))='vodafone' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'device') THEN 'T2_compound_vodafone_device'
      WHEN LOWER(TRIM(r.vendor))='amazon' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'prime\s*video') THEN 'T2_compound_amazon_prime_video'
      WHEN LOWER(TRIM(r.vendor))='bolt' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'stackblitz') THEN 'T2_compound_bolt_stackblitz'
      WHEN LOWER(TRIM(r.vendor))='haven holidays' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'richard\s+haven') THEN 'T2_compound_richard_haven'
      WHEN LOWER(TRIM(r.vendor))='apple store' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'ingle\s+store') THEN 'T2_compound_ingle_store'
      WHEN r.direction='credit' AND (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), r'amazon\s+uk\s+services') OR REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'amazon\s+uk\s+services')) THEN 'T2_compound_amazon_uk_services_salary'
      WHEN LOWER(TRIM(r.vendor))='grosvenor casino' AND r.direction='credit' AND NOT REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'returned|refund(ed)?|reversal of') THEN 'T2_compound_grosvenor_salary'
      WHEN LOWER(TRIM(r.vendor))='admiral' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'casino') THEN 'T2_compound_admiral_casino'
      WHEN LOWER(TRIM(r.vendor))='places for people' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'leisure|nyx|\\bleis\\b') THEN 'T2_compound_places_for_people_leisure'
      WHEN LOWER(TRIM(r.vendor))='nuffield health' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'hospital|clinic|infirmar') THEN 'T2_compound_nuffield_hospital'
      WHEN LOWER(TRIM(r.vendor))='ocado' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'central\\s+serv|ocado\\s+central') THEN 'T2_compound_ocado_salary'
      WHEN LOWER(TRIM(r.vendor))='sodexo' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'healthcare|salary|payroll|wages') THEN 'T2_compound_sodexo_salary'
      WHEN LOWER(TRIM(r.vendor))='ask italian' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'azzurri|salary|payroll|wages|\\bbgc\\b') THEN 'T2_compound_ask_italian_salary'
      WHEN LOWER(TRIM(r.vendor))='fife council' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'bgc|salary|payroll|wages|faster\\s+payment|\\bfps\\b') THEN 'T2_compound_fife_council_salary'
      WHEN LOWER(TRIM(r.vendor))='plum fintech' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'modulo') THEN 'T2_compound_plum_fintech_p2p'
      WHEN LOWER(TRIM(r.vendor))='avon' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'[a-z]{3,}\\s+[a-z]{3,}') THEN 'T2_compound_avon_rep'
      WHEN LOWER(TRIM(r.vendor))='prudential' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'annuity|pension|payout|\\bbgc\\b') THEN 'T2_compound_prudential_payout'
      WHEN LOWER(TRIM(r.vendor))='fluid' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'fluid\\s+focus|\\bto\\s+[a-z]+\\s+[a-z]+') THEN 'T2_compound_fluid_p2p'
      WHEN LOWER(TRIM(r.vendor))='now' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\bentertai\\b') THEN 'T2_compound_now_entertai'
      WHEN LOWER(TRIM(r.vendor))='now' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'paypal') THEN 'T2_compound_now_paypal'
      WHEN LOWER(TRIM(r.vendor))='paypal' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\*now\\b') THEN 'T2_compound_paypal_now'
      WHEN LOWER(TRIM(r.vendor))='paypal' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'payin\\s*3|pay\\s*in\\s*[34]|\\bpayin3\\b|pypl\\s*payin') THEN 'T2_compound_paypal_payin3'
      WHEN LOWER(TRIM(r.vendor))='paypal credit' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'payin\\s*3|pay\\s*in\\s*[34]|\\bpayin3\\b|pypl\\s*payin') THEN 'T2_compound_paypal_credit_payin3'
      WHEN LOWER(TRIM(r.vendor))='paypal' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\*paypal\\s*cre|\\bpaypal\\s*credit\\b') THEN 'T2_compound_paypal_credit_line'
      WHEN LOWER(TRIM(r.vendor))='white lion' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\bhotel\\b') THEN 'T2_compound_white_lion_hotel'
      WHEN LOWER(TRIM(r.vendor))='cts' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'napa|auto\\s+parts|spares') THEN 'T2_compound_cts_napa'
      WHEN LOWER(TRIM(r.vendor))='transferwise' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'via\\s+mobile') THEN 'T2_compound_transferwise_p2p'
      WHEN LOWER(TRIM(r.vendor))='mercedes-benz' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'mbfin|financial') THEN 'T2_compound_mercedes_finance'
      WHEN LOWER(TRIM(r.vendor))='mercedes-benz' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\bof\\s+') THEN 'T2_compound_mercedes_salary'
      WHEN LOWER(TRIM(r.vendor))='mercedes-benz' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\bof\\s+|servic|\\bmot\\b') THEN 'T2_compound_mercedes_dealer'
      WHEN LOWER(TRIM(r.vendor))='the kingfisher' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'convenience|grocer|\\bstore\\b') THEN 'T2_compound_kingfisher_convenience'
      WHEN LOWER(TRIM(r.vendor))='gem' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'gem1|\\bcasino\\b') THEN 'T2_compound_gem_casino'
      WHEN LOWER(TRIM(r.vendor))='gem' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'via\\s+mobile') THEN 'T2_compound_gem_p2p'
      WHEN LOWER(TRIM(r.vendor))='cotswold outdoor' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\d{6,}|salary|payroll|wages') THEN 'T2_compound_cotswold_salary'
      WHEN LOWER(TRIM(r.vendor))='wood j' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'hsm|\\bholiday\\b') THEN 'T2_compound_wood_j_hsm'
      WHEN LOWER(TRIM(r.vendor))='council' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'council\\s+tax') THEN 'T2_compound_council_tax_narrative'
      WHEN LOWER(TRIM(r.vendor))='city' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'city\\s+airport|london\\s+city') THEN 'T2_compound_city_airport'
      WHEN LOWER(TRIM(r.vendor))='city' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'city\\s+council') THEN 'T2_compound_city_council'
      WHEN LOWER(TRIM(r.vendor))='home' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'etsy\\.com|homemadebouti') THEN 'T2_compound_home_etsy'
      WHEN LOWER(TRIM(r.vendor))='home' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'247\\s+home\\s+rescue|home\\s+rescue') THEN 'T2_compound_home_rescue'
      WHEN LOWER(TRIM(r.vendor))='home' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'online\\s+home\\s+shop') THEN 'T2_compound_home_shop'
      WHEN LOWER(TRIM(r.vendor))='home' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'home\\s+glasgow|\\bglasgow\\b') THEN 'T2_compound_home_glasgow'
      WHEN LOWER(TRIM(r.vendor))='orbit' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'credit\\s+services') THEN 'T2_compound_orbit_credit'
      WHEN LOWER(TRIM(r.vendor))='orbit' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'allpay|south\\s+ho|housing|\\brent\\b') THEN 'T2_compound_orbit_rent'
      WHEN LOWER(TRIM(r.vendor))='plus' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'plus500') THEN 'T2_compound_plus500'
      WHEN LOWER(TRIM(r.vendor))='plus' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'direct\\s+debit\\s+plus|plus\\s*finance|plus\\s*loan') THEN 'T2_compound_plus_finance'
      WHEN LOWER(TRIM(r.vendor))='liberty' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\bgas\\b|electric|energy') THEN 'T2_compound_liberty_energy'
      WHEN LOWER(TRIM(r.vendor))='virgin mobile' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'virgin\\s+money') THEN 'T2_compound_virgin_money_on_mobile'
      WHEN LOWER(TRIM(r.vendor))='the grove' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'welwyn|chandler') THEN 'T2_compound_grove_hotel'
      WHEN LOWER(TRIM(r.vendor))='cd glasgow' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sheriff\s+court') THEN 'T2_compound_cd_glasgow_sheriff'
      WHEN LOWER(TRIM(r.vendor))='cd glasgow' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'glasgow\s+central') THEN 'T2_compound_cd_glasgow_central'
      WHEN LOWER(TRIM(r.vendor))='cd glasgow' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'qst\s+stn') THEN 'T2_compound_cd_glasgow_qst'
      WHEN LOWER(TRIM(r.vendor))='cd shop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'schiphol|let\'?s\s+play') THEN 'T2_compound_cd_shop_schiphol'
      WHEN LOWER(TRIM(r.vendor))='cd shop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'khanz') THEN 'T2_compound_cd_shop_khanz'
      WHEN LOWER(TRIM(r.vendor))='cd shop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'shop\s+reading') THEN 'T2_compound_cd_shop_reading'
      WHEN LOWER(TRIM(r.vendor))='foot' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'firstfootsoldiers') THEN 'T2_compound_foot_firstfootsoldiers'
      WHEN LOWER(TRIM(r.vendor))='foot' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'stoke\s+city\s+footbal') THEN 'T2_compound_foot_stoke'
      WHEN LOWER(TRIM(r.vendor))='glossop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'valley\s+cids') THEN 'T2_compound_glossop_cids'
      WHEN LOWER(TRIM(r.vendor))='glossop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'district\s*gol') THEN 'T2_compound_glossop_golf'
      WHEN LOWER(TRIM(r.vendor))='glossop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'glossop\s+sub|sumup\s*\*?\s*glossop\s+sub') THEN 'T2_compound_glossop_subway'
      WHEN LOWER(TRIM(r.vendor))='crawley' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'crawley\.gov') THEN 'T2_compound_crawley_gov'
      WHEN LOWER(TRIM(r.vendor))='crawley' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'black\s+belt') THEN 'T2_compound_crawley_belt'
      WHEN LOWER(TRIM(r.vendor))='track' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'on\s+track|southern\s+ra') THEN 'T2_compound_track_southern'
      WHEN LOWER(TRIM(r.vendor))='track' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'track\s+bandits') THEN 'T2_compound_track_bandits'
      WHEN LOWER(TRIM(r.vendor))='longton' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'service\s+station') THEN 'T2_compound_longton_pfs'
      WHEN LOWER(TRIM(r.vendor))='longton' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'hall\s+farm') THEN 'T2_compound_longton_farm'
      WHEN LOWER(TRIM(r.vendor))='cd stirling' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'costa') THEN 'T2_compound_cd_stirling_costa'
      WHEN LOWER(TRIM(r.vendor))='cd stirling' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'goosecroft') THEN 'T2_compound_cd_stirling_goosecroft'
      WHEN LOWER(TRIM(r.vendor))='cd stirling' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'stirling\s+council|-ips|\bips\b') THEN 'T2_compound_cd_stirling_ips'
      WHEN LOWER(TRIM(r.vendor))='royal victoria' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'infirma') THEN 'T2_compound_royal_victoria_hospital'
      WHEN LOWER(TRIM(r.vendor))='royal victoria' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'country') THEN 'T2_compound_royal_victoria_park'
      WHEN LOWER(TRIM(r.vendor))='cd merlin' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'cinemas?') THEN 'T2_compound_cd_merlin_cinema'
      WHEN LOWER(TRIM(r.vendor))='cd merlin' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'attractions?') THEN 'T2_compound_cd_merlin_attractions'
      WHEN LOWER(TRIM(r.vendor))='cd merlin' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\bderby\b') THEN 'T2_compound_cd_merlin_derby'
      WHEN LOWER(TRIM(r.vendor))='cd colchester' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'leisure') THEN 'T2_compound_cd_colchester_leisure'
      WHEN LOWER(TRIM(r.vendor))='cd colchester' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'borough|-ips|\bips\b') THEN 'T2_compound_cd_colchester_ips'
      WHEN LOWER(TRIM(r.vendor))='cd apex' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'kart') THEN 'T2_compound_cd_apex_kart'
      WHEN LOWER(TRIM(r.vendor))='cd apex' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'harlow') THEN 'T2_compound_cd_apex_harlow'
      WHEN LOWER(TRIM(r.vendor))='cd con' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'coningham') THEN 'T2_compound_cd_con_arms'
      WHEN LOWER(TRIM(r.vendor))='cd con' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'conniburrow') THEN 'T2_compound_cd_con_conniburrow'
      WHEN LOWER(TRIM(r.vendor))='cd miss' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'whippy') THEN 'T2_compound_cd_miss_whippy'
      WHEN LOWER(TRIM(r.vendor))='cd miss' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'glam|aesthetics') THEN 'T2_compound_cd_miss_beauty'
      WHEN LOWER(TRIM(r.vendor))='medical' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'medical\s+aid') THEN 'T2_compound_medical_aid'
      WHEN LOWER(TRIM(r.vendor))='medical' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'bill\s+medical') THEN 'T2_compound_medical_bill'
      WHEN LOWER(TRIM(r.vendor))='medical' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'medical-?supermarket') THEN 'T2_compound_medical_supermarket'
      WHEN LOWER(TRIM(r.vendor))='wardrobe' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'witch') THEN 'T2_compound_wardrobe_witch'
      WHEN LOWER(TRIM(r.vendor))='wardrobe' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'earth\s+wardrobe') THEN 'T2_compound_wardrobe_earth'
      WHEN LOWER(TRIM(r.vendor))='wardrobe' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\bwardrobe\b') THEN 'T2_compound_wardrobe_default'
      WHEN LOWER(TRIM(r.vendor))='cd fresh' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'garbage') THEN 'T2_compound_cd_fresh_garbage'
      WHEN LOWER(TRIM(r.vendor))='cd fresh' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'fresh\s+metro') THEN 'T2_compound_cd_fresh_metro'
      WHEN LOWER(TRIM(r.vendor))='c k' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'knutsford') THEN 'T2_compound_c_k_knutsford'
      WHEN LOWER(TRIM(r.vendor))='c k' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'kremlin') THEN 'T2_compound_c_k_kremlin'
      WHEN LOWER(TRIM(r.vendor))='botany' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'kiosk') THEN 'T2_compound_botany_kiosk'
      WHEN LOWER(TRIM(r.vendor))='botany' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'inn') THEN 'T2_compound_botany_inn'
      WHEN LOWER(TRIM(r.vendor))='afc wigan wallgate' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'northern\s+trains') THEN 'T2_compound_afc_wigan_trains'
      WHEN LOWER(TRIM(r.vendor))='afc wigan wallgate' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'wallgate|afc\s+wigan') THEN 'T2_compound_afc_wigan_takeaway'
      WHEN LOWER(TRIM(r.vendor))='scan' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'scan\.com') THEN 'T2_compound_scan_com'
      WHEN LOWER(TRIM(r.vendor))='scan' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'scandiscents') THEN 'T2_compound_scan_discents'
      WHEN LOWER(TRIM(r.vendor))='mablethorpe' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'grange\s+leisure') THEN 'T2_compound_mablethorpe_grange'
      WHEN LOWER(TRIM(r.vendor))='mablethorpe' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\brock\b') THEN 'T2_compound_mablethorpe_rock'
      WHEN LOWER(TRIM(r.vendor))='wigmore' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'pharmacy') THEN 'T2_compound_wigmore_pharmacy'
      WHEN LOWER(TRIM(r.vendor))='wigmore' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'ppoint|wigmore\s+&\s+ham|gillingham') THEN 'T2_compound_wigmore_ppoint'
      WHEN LOWER(TRIM(r.vendor))='cd alder' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'vets?') THEN 'T2_compound_cd_alder_vets'
      WHEN LOWER(TRIM(r.vendor))='cd alder' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'aldermaston') THEN 'T2_compound_cd_alder_aldermaston'
      WHEN LOWER(TRIM(r.vendor))='cd drum' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'filling\s+station') THEN 'T2_compound_cd_drum_pfs'
      WHEN LOWER(TRIM(r.vendor))='cd drum' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'drum\s+central') THEN 'T2_compound_cd_drum_central'
      WHEN LOWER(TRIM(r.vendor))='c unique' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'petrol') THEN 'T2_compound_c_unique_petrol'
      WHEN LOWER(TRIM(r.vendor))='c unique' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'unique\s+mobile|\bmobile\b') THEN 'T2_compound_c_unique_mobile'
      WHEN LOWER(TRIM(r.vendor))='mexpress uk cd' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'medexpress|med\s*express') THEN 'T2_compound_mexpress_medexpress'
      WHEN LOWER(TRIM(r.vendor))='mexpress uk cd' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'molina') THEN 'T2_compound_mexpress_molina'
      WHEN LOWER(TRIM(r.vendor))='melanie and paul heweston' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'insurance') THEN 'T2_compound_heweston_insurance'
      WHEN LOWER(TRIM(r.vendor))='melanie and paul heweston' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\bloan\b') THEN 'T2_compound_heweston_loan'
      WHEN LOWER(TRIM(r.vendor))='wik' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'maciagowska|repayment') THEN 'T2_compound_wik_repayment'
      WHEN LOWER(TRIM(r.vendor))='wik' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sopel') THEN 'T2_compound_wik_sopel'
      WHEN LOWER(TRIM(r.vendor))='artbox' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'scoop') THEN 'T2_compound_artbox_scoop'
      WHEN LOWER(TRIM(r.vendor))='artbox' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'artbox') THEN 'T2_compound_artbox_shop'
      WHEN LOWER(TRIM(r.vendor))='cd best' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'best4vapes|best\s*4\s*vapes') THEN 'T2_compound_cd_best_vapes'
      WHEN LOWER(TRIM(r.vendor))='cd best' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'best\s+one') THEN 'T2_compound_cd_best_one'
      WHEN LOWER(TRIM(r.vendor))='fitzsimons' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'joshua') THEN 'T2_compound_fitzsimons_joshua'
      WHEN LOWER(TRIM(r.vendor))='fitzsimons' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'fitzsimons') THEN 'T2_compound_fitzsimons_pub'
      WHEN LOWER(TRIM(r.vendor))='banquet' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'paypal') THEN 'T2_compound_banquet_paypal'
      WHEN LOWER(TRIM(r.vendor))='banquet' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sq\s*\*|nottingham') THEN 'T2_compound_banquet_sq'
      WHEN LOWER(TRIM(r.vendor))='thurrock' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'community') THEN 'T2_compound_thurrock_community'
      WHEN LOWER(TRIM(r.vendor))='thurrock' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'borough|-ips') THEN 'T2_compound_thurrock_ips'
      WHEN LOWER(TRIM(r.vendor))='derek' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'wright|loan\s+repayment') THEN 'T2_compound_derek_wright'
      WHEN LOWER(TRIM(r.vendor))='derek' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'derek\s+jones|\bjones\b') THEN 'T2_compound_derek_jones'
      WHEN LOWER(TRIM(r.vendor))='the black' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'black\s+country') THEN 'T2_compound_the_black_chip'
      WHEN LOWER(TRIM(r.vendor))='the black' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'blackheath') THEN 'T2_compound_the_black_heath'
      WHEN LOWER(TRIM(r.vendor))='east bridgford' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'gdn|garden') THEN 'T2_compound_east_bridgford_garden'
      WHEN LOWER(TRIM(r.vendor))='east bridgford' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'medica') THEN 'T2_compound_east_bridgford_medical'
      WHEN LOWER(TRIM(r.vendor))='cd tp' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'amity|kebabs?') THEN 'T2_compound_cd_tp_kebabs'
      WHEN LOWER(TRIM(r.vendor))='cd tp' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'b\s+and\s+j') THEN 'T2_compound_cd_tp_bandj'
      WHEN LOWER(TRIM(r.vendor))='cd no.' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'off\s+licence') THEN 'T2_compound_cd_no_offlicence'
      WHEN LOWER(TRIM(r.vendor))='cd no.' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'no\.?\s*7\s+restaurant|restaurant') THEN 'T2_compound_cd_no_restaurant'
      WHEN LOWER(TRIM(r.vendor))='cd sheffield' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'chaucer') THEN 'T2_compound_cd_sheffield_chaucer'
      WHEN LOWER(TRIM(r.vendor))='cd sheffield' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'meadow') THEN 'T2_compound_cd_sheffield_meadowhall'
      WHEN LOWER(TRIM(r.vendor))='cd green' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'green\s+man') THEN 'T2_compound_cd_green_man'
      WHEN LOWER(TRIM(r.vendor))='cd green' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'green\s+valley') THEN 'T2_compound_cd_green_valley'
      WHEN LOWER(TRIM(r.vendor))='egg' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'zettle|eggbugland') THEN 'T2_compound_egg_zettle'
      WHEN LOWER(TRIM(r.vendor))='egg' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'162224|direct\s+debit|\begg\b') THEN 'T2_compound_egg_energy'
      WHEN LOWER(TRIM(r.vendor))='jasmine' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'restaurant') THEN 'T2_compound_jasmine_restaurant'
      WHEN LOWER(TRIM(r.vendor))='jasmine' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'chesney|sortcode|\d{10,}') THEN 'T2_compound_jasmine_p2p'
      WHEN LOWER(TRIM(r.vendor))='paymy.vet' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'groom') THEN 'T2_compound_paymyvet_groom'
      WHEN LOWER(TRIM(r.vendor))='paymy.vet' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'vets?|bolton') THEN 'T2_compound_paymyvet_vets'
      WHEN LOWER(TRIM(r.vendor))='bill\'s' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'nanny') THEN 'T2_compound_bills_nanny'
      WHEN LOWER(TRIM(r.vendor))='bill\'s' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'mcgill|buses') THEN 'T2_compound_bills_bus'
      WHEN LOWER(TRIM(r.vendor))='bill\'s' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'restaurant') THEN 'T2_compound_bills_restaurant'
      WHEN LOWER(TRIM(r.vendor))='reddish' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'service\s+stati') THEN 'T2_compound_reddish_pfs'
      WHEN LOWER(TRIM(r.vendor))='reddish' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'convenience') THEN 'T2_compound_reddish_shop'
      WHEN LOWER(TRIM(r.vendor))='hafod' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sq\s*\*') THEN 'T2_compound_hafod_sq'
      WHEN LOWER(TRIM(r.vendor))='hafod' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'housing') THEN 'T2_compound_hafod_housing'
      WHEN LOWER(TRIM(r.vendor))='hart' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'hart\s+il|sortcode') THEN 'T2_compound_hart_il'
      WHEN LOWER(TRIM(r.vendor))='hart' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'district\s+council|\bcouncil\b') THEN 'T2_compound_hart_council'
      WHEN LOWER(TRIM(r.vendor))='blackwell\'s' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sammy|k\s+a\s+blackwell') THEN 'T2_compound_blackwells_p2p'
      WHEN LOWER(TRIM(r.vendor))='blackwell\'s' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'blackwell') THEN 'T2_compound_blackwells_books'
      WHEN LOWER(TRIM(r.vendor))='gamesys operation' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'gamesys') THEN 'T2_compound_gamesys_unspecified'
      WHEN LOWER(TRIM(r.vendor))='the ups store' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'ppoint|g\s+and\s+s\s+stores') THEN 'T2_compound_ups_ppoint'
      WHEN LOWER(TRIM(r.vendor))='the ups store' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'ups\s+store') THEN 'T2_compound_ups_store'
      WHEN LOWER(TRIM(r.vendor))='hiba' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'bibs|bakri|clothing') THEN 'T2_compound_hiba_bibs'
      WHEN LOWER(TRIM(r.vendor))='hiba' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sagheer') THEN 'T2_compound_hiba_sagheer'
      WHEN LOWER(TRIM(r.vendor))='collection pot' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'collection\s+pot') THEN 'T2_compound_collection_pot_dining'
      WHEN LOWER(TRIM(r.vendor))='wirral mbc' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\batp\b') THEN 'T2_compound_wirral_atp'
      WHEN LOWER(TRIM(r.vendor))='wirral mbc' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'wirral\s+mbc') THEN 'T2_compound_wirral_council'
      WHEN LOWER(TRIM(r.vendor))='barbican' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'news') THEN 'T2_compound_barbican_news'
      WHEN LOWER(TRIM(r.vendor))='barbican' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'barbican') THEN 'T2_compound_barbican_theatre'
      WHEN LOWER(TRIM(r.vendor))='wine lodge' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'ppoint') THEN 'T2_compound_wine_lodge_ppoint'
      WHEN LOWER(TRIM(r.vendor))='wine lodge' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'wine\s+lodge') THEN 'T2_compound_wine_lodge_pub'
      WHEN LOWER(TRIM(r.vendor))='pier' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'fish|chips') THEN 'T2_compound_pier_chips'
      WHEN LOWER(TRIM(r.vendor))='pier' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'pieralongia') THEN 'T2_compound_pier_p2p'
      WHEN LOWER(TRIM(r.vendor))='pier' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'pier\s+36|donaghadee') THEN 'T2_compound_pier_36'
      WHEN LOWER(TRIM(r.vendor))='amber valley borough council' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'-ips|\bips\b') THEN 'T2_compound_amber_valley_ips'
      WHEN LOWER(TRIM(r.vendor))='roadchef' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'whsmi') THEN 'T2_compound_roadchef_whsmith'
      WHEN LOWER(TRIM(r.vendor))='wembley park' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'expre') THEN 'T2_compound_wembley_park_express'
      WHEN LOWER(TRIM(r.vendor))='rbs-natwest w/end credit' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'recollection|monzo') THEN 'T2_compound_natwest_westend_recollection'
      WHEN r.pri IN ('Identified Salary','Refund','Benefits','Welfare','Pension Payout','Tax Refund',
        'Cash Back','Cash Machine','Cash Deposit','Interest','Interests and Dividends',
        'Balance Transfers','Adjustments') THEN 'T3_mechanism_override'
      WHEN r.direction='credit' AND d.leaf IN ('gambling_betting', 'gambling_casino', 'gambling_bingo', 'gambling_lottery') THEN 'T1_direction_gambling_credit'
      WHEN r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\brefund(ed)?\b') AND (d.leaf IS NULL OR d.leaf NOT IN ('gambling_betting', 'gambling_casino', 'gambling_bingo', 'gambling_lottery')) THEN 'T2_compound_refund'
      WHEN r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'returned\s+(direct\s+debit|standing\s+order)|direct\s+debit\s+reversal|\breversal of\b') THEN 'T2_compound_returned_payment'
      WHEN LOWER(TRIM(r.vendor))='youlend' AND r.direction='credit' THEN 'T2_compound_youlend_disbursement'
      WHEN d.leaf IS NOT NULL THEN 'T4_merchant_dictionary'
      WHEN REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '^(mr|mrs|miss|ms|dr)\\s+') THEN 'T5_rule_R01'
      WHEN REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '^[a-z]\\s+[a-z]{2,}$') THEN 'T5_rule_R02'
      WHEN REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), CONCAT(r'\b(', 'mum|dad|mom|nan|nana|gran|granny|grandad|sister|brother|son|daughter|wife|husband', r')\b')) THEN 'T5_rule_R03'
      WHEN REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '^exchanged to (btc|eth|sol|xrp|ada|doge)') THEN 'T5_rule_R04'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '(petrol|fuel)\\s*(station)?$') AND r.direction = 'debit') THEN 'T5_rule_R05'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '(bingo|casino)') AND r.direction = 'debit') THEN 'T5_rule_R06'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '\\b(bet|betting|bookmaker)\\b|\\bbet\\s?\\d\\d+\\b|\\b(sky|uni|coral|lad|net|virgin|paddy|smark)bet\\b|\\bbet(fred|fair|victor|way|uk|bright)\\b') AND r.direction = 'debit') THEN 'T5_rule_R07'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '\\b(lottery|lotto)\\b') AND r.direction = 'debit') THEN 'T5_rule_R08'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '\\b(debt (collection|recovery)|collections? ltd)\\b') AND r.direction = 'debit') THEN 'T5_rule_R14'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), CONCAT(r'\b(', 'child maintenance', r')\b')) AND r.direction = 'credit') THEN 'T5_rule_R15'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), CONCAT(r'\b(', 'we buy any car', r')\b')) AND r.direction = 'credit') THEN 'T5_rule_R16'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), CONCAT(r'\b(', 'we buy any car', r')\b')) AND r.direction = 'debit') THEN 'T5_rule_R17'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '\\b(payday(?:\\s*loans?)?|wonga|quick\\s?quid|lending\\s?stream|118\\s*(?:118\\s*)?money|cashfloat|quid\\s?market|morses\\s?club|moneyboat|tick\\s?tock\\s*loans?|sunny\\s+loans?|cash\\s?asap|fast\\s+loan)\\b') AND r.direction = 'debit') THEN 'T5_rule_R18'
      WHEN ((REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '\\bmorr\\b') AND NOT REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), 'petrol|pfs|fuel|caf[eé]')) AND r.direction = 'debit') THEN 'T5_rule_R21'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '\\bwages\\b') AND r.direction = 'credit') THEN 'T5_rule_R26'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '\\boff\\s+licence\\b') AND r.direction = 'debit') THEN 'T5_rule_R30'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '\\b(car park|parking)\\b') AND r.direction = 'debit') THEN 'T5_rule_R09'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '\\b(vets?|veterinary)\\b') AND r.direction = 'debit') THEN 'T5_rule_R10'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.vendor)), '\\b(pharmacy|chemist)\\b') AND r.direction = 'debit') THEN 'T5_rule_R11'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bcouncil tax\\b') AND r.direction = 'debit') THEN 'T5_rule_R12'
      WHEN ((REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\b(rent|landlord)\\b') AND NOT REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), 'rent\\s*/\\s*buy|video rent|rent.?a.?car')) AND r.direction = 'debit') THEN 'T5_rule_R13'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\b(payday(?:\\s*loans?)?|wonga|quick\\s?quid|lending\\s?stream|118\\s*(?:118\\s*)?money|cashfloat|quid\\s?market|morses\\s?club|moneyboat|tick\\s?tock\\s*loans?|sunny\\s+loans?|cash\\s?asap|fast\\s+loan)\\b') AND r.direction = 'debit') THEN 'T5_rule_R19'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bexpo international\\s+sup') AND r.direction = 'debit') THEN 'T5_rule_R20'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bsheriff\\s+court\\b') AND r.direction = 'debit') THEN 'T5_rule_R22'
      WHEN ((REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\b(universal\\s+credit|dwp\\s+uc\\b|dwp\\s+eesa|dwp\\s+pc\\b|pension\\s+credit|child\\s+benefits?|work(?:ing)?\\s+and\\s+child\\s+(?:tc|tax)|child\\s+tax\\s+credit|working\\s+tax\\s+credit|carers?\\s+allowance|disability\\s+living\\s+allowance|personal\\s+independence\\s+payment|employment\\s+and\\s+support\\s+allowance)\\b') AND NOT REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), 'debt|recovery|cms|maintenance|enforcement')) AND r.direction = 'credit') THEN 'T5_rule_R23'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bscholastic\\s+book') AND r.direction = 'debit') THEN 'T5_rule_R24'
      WHEN ((REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bwages\\b') AND NOT REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), 'minimum\\s+wage|living\\s+wage')) AND r.direction = 'credit') THEN 'T5_rule_R25'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bentertai\\b') AND r.direction = 'debit') THEN 'T5_rule_R27'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), 'paypal\\s*\\*now') AND r.direction = 'debit') THEN 'T5_rule_R28'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\boff\\s+licence\\b') AND r.direction = 'debit') THEN 'T5_rule_R29'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bstep[\\s-]*change\\b') AND r.direction = 'debit') THEN 'T5_rule_R31'
      WHEN ((REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bpaypal\\s*\\*?\\s*paypal\\s*cre|\\bpaypal\\s+credit\\b') AND NOT REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), 'payin\\s*3|pay\\s*in\\s*[34]|\\bpayin3\\b|pypl\\s*payin')) AND r.direction = 'debit') THEN 'T5_rule_R32'
      WHEN s.leaf IS NOT NULL THEN 'T6_provider_crosswalk'
      WHEN p.leaf IS NOT NULL THEN 'T6_provider_crosswalk'
      ELSE 'T7_unclassified'
    END AS resolution_tier
  FROM eqx_raw r
  LEFT JOIN sub_xw s ON r.sub = s.eqx_sub
  LEFT JOIN pri_xw p ON r.pri = p.eqx_pri
  LEFT JOIN dict_xw d ON LOWER(TRIM(r.vendor)) = d.merchant
),

-- ---------- PLAID ----------
plaid_raw AS (
  SELECT credit_category_detailed AS cat,
         merchant_name AS merchant_raw,
         COALESCE(original_description, transaction_name) AS description_raw,
         IF(amount < 0,'credit','debit') AS direction, amount AS Amount
  FROM `raylo-production.dbt_production.credit_plaid_open_banking_transactions`
  TABLESAMPLE SYSTEM (20 PERCENT)
),
plaid_resolved AS (
  SELECT r.*,
    CASE
      -- T1: direction-dependent overrides
      WHEN r.cat='ENTERTAINMENT_CASINOS_AND_GAMBLING' AND r.direction='credit' THEN 'gambling_unspecified'
      -- T2: provider-entity collisions -- see eqx_resolved
      WHEN LOWER(TRIM(r.merchant_raw))='tesco' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\btesco bank\b') THEN 'financial_institution_unspecified'
      WHEN LOWER(TRIM(r.merchant_raw))='tesco' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'tescophoneins') THEN 'insurance_other'
      WHEN LOWER(TRIM(r.merchant_raw))='tesco' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'caf[eé]') THEN 'restaurant_cafe'
      WHEN LOWER(TRIM(r.merchant_raw)) IN ('tesco', 'one stop', 'post office', 'u.s. post office', 'asda', 'sainsbury\'s', 'co-op') AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\batm\b|\blnk\b|cash\s+at\b|cash\s+withdrawal') THEN 'cash_withdrawal'
      WHEN LOWER(TRIM(r.merchant_raw)) IN ('tesco', 'one stop', 'post office', 'u.s. post office', 'asda', 'sainsbury\'s', 'co-op') AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\batm\b|cash\s+deposit') THEN 'cash_deposit'
      WHEN LOWER(TRIM(r.merchant_raw))='tesco' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'petrol|\bpfs\b|\bfuel\b') THEN 'fuel'
      WHEN LOWER(TRIM(r.merchant_raw)) IN ('morr', 'cd morr') AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'caf[eé]') THEN 'restaurant_cafe'
      WHEN LOWER(TRIM(r.merchant_raw)) IN ('co-op', 'sainsbury\'s', 'asda', 'morr', 'cd morr') AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'petrol|\bpfs\b|\bfuel\b') THEN 'fuel'
      WHEN LOWER(TRIM(r.merchant_raw)) IN ('hmrc', 'hm revenue and customs') AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'child\s+benefits?') THEN 'benefits_state'
      WHEN LOWER(TRIM(r.merchant_raw)) IN ('hmrc', 'hm revenue and customs') AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'work(?:ing)?\s+and\s+child\s+(?:tax\s+)?credits?|work(?:ing)?\s+and\s+child\s+tc\b|child\s+tax\s+credits?|working\s+tax\s+credits?') THEN 'benefits_state'
      WHEN LOWER(TRIM(r.merchant_raw)) IN ('hmrc', 'hm revenue and customs') AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\bhmrc\s+sa\b|\bgov\.uk\s+sa\b|\bself[\s-]*assess') THEN 'tax_refund'
      WHEN r.direction='debit' AND (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), r'\bkfc\b') OR REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\bkfc\b')) THEN 'takeaway'
      WHEN LOWER(TRIM(r.merchant_raw))='tiktok' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'tiktok\s*shop|\bshop\s*seller') THEN 'marketplace_general'
      WHEN LOWER(TRIM(r.merchant_raw))='tiktok' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'shop\s*seller') THEN 'income_other_unspecified'
      WHEN LOWER(TRIM(r.merchant_raw))='sky' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sky\s*protect|\bdgi\b.*protect|protect.*\bdgi\b') THEN 'insurance_other'
      WHEN LOWER(TRIM(r.merchant_raw))='child benefits' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'dwp\s*cms|dwpcms|cmsgb2012|child\s+maintenance') THEN 'income_other_unspecified'
      WHEN LOWER(TRIM(r.merchant_raw))='asda' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'asda\s*mobile') THEN 'mobile_phone_contract'
      WHEN LOWER(TRIM(r.merchant_raw))='asda' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'asda\s*living') THEN 'home_accessories'
      WHEN LOWER(TRIM(r.merchant_raw))='vodafone' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'device') THEN 'mobile_handset'
      WHEN LOWER(TRIM(r.merchant_raw))='amazon' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'prime\s*video') THEN 'streaming'
      WHEN LOWER(TRIM(r.merchant_raw))='bolt' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'stackblitz') THEN 'software'
      WHEN LOWER(TRIM(r.merchant_raw))='haven holidays' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'richard\s+haven') THEN 'beauty_treatment'
      WHEN LOWER(TRIM(r.merchant_raw))='apple store' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'ingle\s+store') THEN 'convenience_store'
      WHEN r.direction='credit' AND (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), r'amazon\s+uk\s+services') OR REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'amazon\s+uk\s+services')) THEN 'salary'
      WHEN LOWER(TRIM(r.merchant_raw))='grosvenor casino' AND r.direction='credit' AND NOT REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'returned|refund(ed)?|reversal of') THEN 'salary'
      WHEN LOWER(TRIM(r.merchant_raw))='admiral' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'casino') THEN 'gambling_casino'
      WHEN LOWER(TRIM(r.merchant_raw))='places for people' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'leisure|nyx|\\bleis\\b') THEN 'gym_fitness'
      WHEN LOWER(TRIM(r.merchant_raw))='nuffield health' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'hospital|clinic|infirmar') THEN 'hospital'
      WHEN LOWER(TRIM(r.merchant_raw))='ocado' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'central\\s+serv|ocado\\s+central') THEN 'salary'
      WHEN LOWER(TRIM(r.merchant_raw))='sodexo' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'healthcare|salary|payroll|wages') THEN 'salary'
      WHEN LOWER(TRIM(r.merchant_raw))='ask italian' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'azzurri|salary|payroll|wages|\\bbgc\\b') THEN 'salary'
      WHEN LOWER(TRIM(r.merchant_raw))='fife council' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'bgc|salary|payroll|wages|faster\\s+payment|\\bfps\\b') THEN 'salary'
      WHEN LOWER(TRIM(r.merchant_raw))='plum fintech' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'modulo') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.merchant_raw))='avon' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'[a-z]{3,}\\s+[a-z]{3,}') THEN 'income_other_unspecified'
      WHEN LOWER(TRIM(r.merchant_raw))='prudential' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'annuity|pension|payout|\\bbgc\\b') THEN 'pension_received'
      WHEN LOWER(TRIM(r.merchant_raw))='fluid' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'fluid\\s+focus|\\bto\\s+[a-z]+\\s+[a-z]+') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.merchant_raw))='now' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\bentertai\\b') THEN 'streaming'
      WHEN LOWER(TRIM(r.merchant_raw))='now' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'paypal') THEN 'streaming'
      WHEN LOWER(TRIM(r.merchant_raw))='paypal' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\*now\\b') THEN 'streaming'
      WHEN LOWER(TRIM(r.merchant_raw))='paypal' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'payin\\s*3|pay\\s*in\\s*[34]|\\bpayin3\\b|pypl\\s*payin') THEN 'bnpl'
      WHEN LOWER(TRIM(r.merchant_raw))='paypal credit' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'payin\\s*3|pay\\s*in\\s*[34]|\\bpayin3\\b|pypl\\s*payin') THEN 'bnpl'
      WHEN LOWER(TRIM(r.merchant_raw))='paypal' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\*paypal\\s*cre|\\bpaypal\\s*credit\\b') THEN 'revolving_credit_repayment'
      WHEN LOWER(TRIM(r.merchant_raw))='white lion' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\bhotel\\b') THEN 'accommodation'
      WHEN LOWER(TRIM(r.merchant_raw))='cts' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'napa|auto\\s+parts|spares') THEN 'spares_repairs'
      WHEN LOWER(TRIM(r.merchant_raw))='transferwise' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'via\\s+mobile') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.merchant_raw))='mercedes-benz' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'mbfin|financial') THEN 'car_finance_repayment'
      WHEN LOWER(TRIM(r.merchant_raw))='mercedes-benz' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\bof\\s+') THEN 'salary'
      WHEN LOWER(TRIM(r.merchant_raw))='mercedes-benz' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\bof\\s+|servic|\\bmot\\b') THEN 'vehicle_servicing'
      WHEN LOWER(TRIM(r.merchant_raw))='the kingfisher' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'convenience|grocer|\\bstore\\b') THEN 'convenience_store'
      WHEN LOWER(TRIM(r.merchant_raw))='gem' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'gem1|\\bcasino\\b') THEN 'gambling_casino'
      WHEN LOWER(TRIM(r.merchant_raw))='gem' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'via\\s+mobile') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.merchant_raw))='cotswold outdoor' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\d{6,}|salary|payroll|wages') THEN 'salary'
      WHEN LOWER(TRIM(r.merchant_raw))='wood j' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'hsm|\\bholiday\\b') THEN 'holiday_package'
      WHEN LOWER(TRIM(r.merchant_raw))='council' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'council\\s+tax') THEN 'council_tax'
      WHEN LOWER(TRIM(r.merchant_raw))='city' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'city\\s+airport|london\\s+city') THEN 'airport_spend'
      WHEN LOWER(TRIM(r.merchant_raw))='city' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'city\\s+council') THEN 'government_services'
      WHEN LOWER(TRIM(r.merchant_raw))='home' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'etsy\\.com|homemadebouti') THEN 'gifts_flowers'
      WHEN LOWER(TRIM(r.merchant_raw))='home' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'247\\s+home\\s+rescue|home\\s+rescue') THEN 'home_repair'
      WHEN LOWER(TRIM(r.merchant_raw))='home' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'online\\s+home\\s+shop') THEN 'home_accessories'
      WHEN LOWER(TRIM(r.merchant_raw))='home' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'home\\s+glasgow|\\bglasgow\\b') THEN 'mortgage'
      WHEN LOWER(TRIM(r.merchant_raw))='orbit' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'credit\\s+services') THEN 'debt_collection'
      WHEN LOWER(TRIM(r.merchant_raw))='orbit' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'allpay|south\\s+ho|housing|\\brent\\b') THEN 'rent'
      WHEN LOWER(TRIM(r.merchant_raw))='plus' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'plus500') THEN 'investment_trading'
      WHEN LOWER(TRIM(r.merchant_raw))='plus' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'direct\\s+debit\\s+plus|plus\\s*finance|plus\\s*loan') THEN 'personal_loan_repayment'
      WHEN LOWER(TRIM(r.merchant_raw))='liberty' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\bgas\\b|electric|energy') THEN 'energy'
      WHEN LOWER(TRIM(r.merchant_raw))='virgin mobile' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'virgin\\s+money') THEN 'credit_card_repayment'
      WHEN LOWER(TRIM(r.merchant_raw))='the grove' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'welwyn|chandler') THEN 'accommodation'
      WHEN LOWER(TRIM(r.merchant_raw))='cd glasgow' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sheriff\s+court') THEN 'government_services'
      WHEN LOWER(TRIM(r.merchant_raw))='cd glasgow' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'glasgow\s+central') THEN 'public_transport_rail_coach'
      WHEN LOWER(TRIM(r.merchant_raw))='cd glasgow' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'qst\s+stn') THEN 'public_transport_rail_coach'
      WHEN LOWER(TRIM(r.merchant_raw))='cd shop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'schiphol|let\'?s\s+play') THEN 'airport_spend'
      WHEN LOWER(TRIM(r.merchant_raw))='cd shop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'khanz') THEN 'convenience_store'
      WHEN LOWER(TRIM(r.merchant_raw))='cd shop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'shop\s+reading') THEN 'retail_other'
      WHEN LOWER(TRIM(r.merchant_raw))='foot' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'firstfootsoldiers') THEN 'entertainment_other'
      WHEN LOWER(TRIM(r.merchant_raw))='foot' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'stoke\s+city\s+footbal') THEN 'sports_tickets'
      WHEN LOWER(TRIM(r.merchant_raw))='glossop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'valley\s+cids') THEN 'charitable_donation'
      WHEN LOWER(TRIM(r.merchant_raw))='glossop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'district\s*gol') THEN 'sports_participation'
      WHEN LOWER(TRIM(r.merchant_raw))='glossop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'glossop\s+sub|sumup\s*\*?\s*glossop\s+sub') THEN 'takeaway'
      WHEN LOWER(TRIM(r.merchant_raw))='crawley' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'crawley\.gov') THEN 'government_services'
      WHEN LOWER(TRIM(r.merchant_raw))='crawley' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'black\s+belt') THEN 'sports_participation'
      WHEN LOWER(TRIM(r.merchant_raw))='track' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'on\s+track|southern\s+ra') THEN 'public_transport_rail_coach'
      WHEN LOWER(TRIM(r.merchant_raw))='track' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'track\s+bandits') THEN 'clothing_general'
      WHEN LOWER(TRIM(r.merchant_raw))='longton' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'service\s+station') THEN 'fuel'
      WHEN LOWER(TRIM(r.merchant_raw))='longton' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'hall\s+farm') THEN 'car_parking'
      WHEN LOWER(TRIM(r.merchant_raw))='cd stirling' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'costa') THEN 'restaurant_cafe'
      WHEN LOWER(TRIM(r.merchant_raw))='cd stirling' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'goosecroft') THEN 'car_parking'
      WHEN LOWER(TRIM(r.merchant_raw))='cd stirling' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'stirling\s+council|-ips|\bips\b') THEN 'car_parking'
      WHEN LOWER(TRIM(r.merchant_raw))='royal victoria' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'infirma') THEN 'hospital'
      WHEN LOWER(TRIM(r.merchant_raw))='royal victoria' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'country') THEN 'days_out'
      WHEN LOWER(TRIM(r.merchant_raw))='cd merlin' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'cinemas?') THEN 'cinema'
      WHEN LOWER(TRIM(r.merchant_raw))='cd merlin' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'attractions?') THEN 'days_out'
      WHEN LOWER(TRIM(r.merchant_raw))='cd merlin' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\bderby\b') THEN 'entertainment_other'
      WHEN LOWER(TRIM(r.merchant_raw))='cd colchester' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'leisure') THEN 'sports_participation'
      WHEN LOWER(TRIM(r.merchant_raw))='cd colchester' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'borough|-ips|\bips\b') THEN 'car_parking'
      WHEN LOWER(TRIM(r.merchant_raw))='cd apex' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'kart') THEN 'days_out'
      WHEN LOWER(TRIM(r.merchant_raw))='cd apex' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'harlow') THEN 'business_services'
      WHEN LOWER(TRIM(r.merchant_raw))='cd con' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'coningham') THEN 'pub_bar'
      WHEN LOWER(TRIM(r.merchant_raw))='cd con' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'conniburrow') THEN 'unclassified_card_spend'
      WHEN LOWER(TRIM(r.merchant_raw))='cd miss' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'whippy') THEN 'takeaway'
      WHEN LOWER(TRIM(r.merchant_raw))='cd miss' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'glam|aesthetics') THEN 'beauty_treatment'
      WHEN LOWER(TRIM(r.merchant_raw))='medical' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'medical\s+aid') THEN 'charitable_donation'
      WHEN LOWER(TRIM(r.merchant_raw))='medical' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'bill\s+medical') THEN 'health_other'
      WHEN LOWER(TRIM(r.merchant_raw))='medical' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'medical-?supermarket') THEN 'pharmacy'
      WHEN LOWER(TRIM(r.merchant_raw))='wardrobe' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'witch') THEN 'pub_bar'
      WHEN LOWER(TRIM(r.merchant_raw))='wardrobe' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'earth\s+wardrobe') THEN 'clothing_general'
      WHEN LOWER(TRIM(r.merchant_raw))='wardrobe' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\bwardrobe\b') THEN 'clothing_general'
      WHEN LOWER(TRIM(r.merchant_raw))='cd fresh' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'garbage') THEN 'clothing_general'
      WHEN LOWER(TRIM(r.merchant_raw))='cd fresh' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'fresh\s+metro') THEN 'groceries'
      WHEN LOWER(TRIM(r.merchant_raw))='c k' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'knutsford') THEN 'restaurant_cafe'
      WHEN LOWER(TRIM(r.merchant_raw))='c k' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'kremlin') THEN 'pub_bar'
      WHEN LOWER(TRIM(r.merchant_raw))='botany' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'kiosk') THEN 'takeaway'
      WHEN LOWER(TRIM(r.merchant_raw))='botany' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'inn') THEN 'pub_bar'
      WHEN LOWER(TRIM(r.merchant_raw))='afc wigan wallgate' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'northern\s+trains') THEN 'public_transport_rail_coach'
      WHEN LOWER(TRIM(r.merchant_raw))='afc wigan wallgate' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'wallgate|afc\s+wigan') THEN 'takeaway'
      WHEN LOWER(TRIM(r.merchant_raw))='scan' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'scan\.com') THEN 'health_other'
      WHEN LOWER(TRIM(r.merchant_raw))='scan' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'scandiscents') THEN 'home_accessories'
      WHEN LOWER(TRIM(r.merchant_raw))='mablethorpe' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'grange\s+leisure') THEN 'accommodation'
      WHEN LOWER(TRIM(r.merchant_raw))='mablethorpe' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\brock\b') THEN 'confectionary'
      WHEN LOWER(TRIM(r.merchant_raw))='wigmore' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'pharmacy') THEN 'pharmacy'
      WHEN LOWER(TRIM(r.merchant_raw))='wigmore' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'ppoint|wigmore\s+&\s+ham|gillingham') THEN 'convenience_store'
      WHEN LOWER(TRIM(r.merchant_raw))='cd alder' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'vets?') THEN 'veterinary'
      WHEN LOWER(TRIM(r.merchant_raw))='cd alder' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'aldermaston') THEN 'fuel'
      WHEN LOWER(TRIM(r.merchant_raw))='cd drum' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'filling\s+station') THEN 'fuel'
      WHEN LOWER(TRIM(r.merchant_raw))='cd drum' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'drum\s+central') THEN 'musical_instruments'
      WHEN LOWER(TRIM(r.merchant_raw))='c unique' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'petrol') THEN 'fuel'
      WHEN LOWER(TRIM(r.merchant_raw))='c unique' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'unique\s+mobile|\bmobile\b') THEN 'mobile_handset'
      WHEN LOWER(TRIM(r.merchant_raw))='mexpress uk cd' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'medexpress|med\s*express') THEN 'pharmacy'
      WHEN LOWER(TRIM(r.merchant_raw))='mexpress uk cd' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'molina') THEN 'delivery_courier'
      WHEN LOWER(TRIM(r.merchant_raw))='melanie and paul heweston' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'insurance') THEN 'insurance_general'
      WHEN LOWER(TRIM(r.merchant_raw))='melanie and paul heweston' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\bloan\b') THEN 'loan_repayment_manual'
      WHEN LOWER(TRIM(r.merchant_raw))='wik' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'maciagowska|repayment') THEN 'loan_repayment_manual'
      WHEN LOWER(TRIM(r.merchant_raw))='wik' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sopel') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.merchant_raw))='artbox' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'scoop') THEN 'restaurant_cafe'
      WHEN LOWER(TRIM(r.merchant_raw))='artbox' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'artbox') THEN 'stationery'
      WHEN LOWER(TRIM(r.merchant_raw))='cd best' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'best4vapes|best\s*4\s*vapes') THEN 'vaping'
      WHEN LOWER(TRIM(r.merchant_raw))='cd best' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'best\s+one') THEN 'convenience_store'
      WHEN LOWER(TRIM(r.merchant_raw))='fitzsimons' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'joshua') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.merchant_raw))='fitzsimons' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'fitzsimons') THEN 'pub_bar'
      WHEN LOWER(TRIM(r.merchant_raw))='banquet' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'paypal') THEN 'music_other'
      WHEN LOWER(TRIM(r.merchant_raw))='banquet' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sq\s*\*|nottingham') THEN 'restaurant_cafe'
      WHEN LOWER(TRIM(r.merchant_raw))='thurrock' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'community') THEN 'government_services'
      WHEN LOWER(TRIM(r.merchant_raw))='thurrock' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'borough|-ips') THEN 'car_parking'
      WHEN LOWER(TRIM(r.merchant_raw))='derek' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'wright|loan\s+repayment') THEN 'loan_repayment_manual'
      WHEN LOWER(TRIM(r.merchant_raw))='derek' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'derek\s+jones|\bjones\b') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.merchant_raw))='the black' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'black\s+country') THEN 'takeaway'
      WHEN LOWER(TRIM(r.merchant_raw))='the black' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'blackheath') THEN 'pub_bar'
      WHEN LOWER(TRIM(r.merchant_raw))='east bridgford' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'gdn|garden') THEN 'garden'
      WHEN LOWER(TRIM(r.merchant_raw))='east bridgford' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'medica') THEN 'health_other'
      WHEN LOWER(TRIM(r.merchant_raw))='cd tp' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'amity|kebabs?') THEN 'takeaway'
      WHEN LOWER(TRIM(r.merchant_raw))='cd tp' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'b\s+and\s+j') THEN 'convenience_store'
      WHEN LOWER(TRIM(r.merchant_raw))='cd no.' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'off\s+licence') THEN 'alcohol_beer_spirits'
      WHEN LOWER(TRIM(r.merchant_raw))='cd no.' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'no\.?\s*7\s+restaurant|restaurant') THEN 'restaurant_cafe'
      WHEN LOWER(TRIM(r.merchant_raw))='cd sheffield' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'chaucer') THEN 'convenience_store'
      WHEN LOWER(TRIM(r.merchant_raw))='cd sheffield' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'meadow') THEN 'retail_other'
      WHEN LOWER(TRIM(r.merchant_raw))='cd green' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'green\s+man') THEN 'pub_bar'
      WHEN LOWER(TRIM(r.merchant_raw))='cd green' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'green\s+valley') THEN 'groceries'
      WHEN LOWER(TRIM(r.merchant_raw))='egg' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'zettle|eggbugland') THEN 'retail_other'
      WHEN LOWER(TRIM(r.merchant_raw))='egg' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'162224|direct\s+debit|\begg\b') THEN 'energy'
      WHEN LOWER(TRIM(r.merchant_raw))='jasmine' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'restaurant') THEN 'restaurant_cafe'
      WHEN LOWER(TRIM(r.merchant_raw))='jasmine' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'chesney|sortcode|\d{10,}') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.merchant_raw))='paymy.vet' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'groom') THEN 'pet_other'
      WHEN LOWER(TRIM(r.merchant_raw))='paymy.vet' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'vets?|bolton') THEN 'veterinary'
      WHEN LOWER(TRIM(r.merchant_raw))='bill\'s' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'nanny') THEN 'takeaway'
      WHEN LOWER(TRIM(r.merchant_raw))='bill\'s' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'mcgill|buses') THEN 'public_transport_rail_coach'
      WHEN LOWER(TRIM(r.merchant_raw))='bill\'s' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'restaurant') THEN 'restaurant_cafe'
      WHEN LOWER(TRIM(r.merchant_raw))='reddish' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'service\s+stati') THEN 'fuel'
      WHEN LOWER(TRIM(r.merchant_raw))='reddish' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'convenience') THEN 'convenience_store'
      WHEN LOWER(TRIM(r.merchant_raw))='hafod' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sq\s*\*') THEN 'restaurant_cafe'
      WHEN LOWER(TRIM(r.merchant_raw))='hafod' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'housing') THEN 'rent'
      WHEN LOWER(TRIM(r.merchant_raw))='hart' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'hart\s+il|sortcode') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.merchant_raw))='hart' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'district\s+council|\bcouncil\b') THEN 'council_tax'
      WHEN LOWER(TRIM(r.merchant_raw))='blackwell\'s' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sammy|k\s+a\s+blackwell') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.merchant_raw))='blackwell\'s' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'blackwell') THEN 'books'
      WHEN LOWER(TRIM(r.merchant_raw))='gamesys operation' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'gamesys') THEN 'gambling_unspecified'
      WHEN LOWER(TRIM(r.merchant_raw))='the ups store' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'ppoint|g\s+and\s+s\s+stores') THEN 'convenience_store'
      WHEN LOWER(TRIM(r.merchant_raw))='the ups store' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'ups\s+store') THEN 'delivery_courier'
      WHEN LOWER(TRIM(r.merchant_raw))='hiba' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'bibs|bakri|clothing') THEN 'clothing_general'
      WHEN LOWER(TRIM(r.merchant_raw))='hiba' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sagheer') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.merchant_raw))='collection pot' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'collection\s+pot') THEN 'restaurant_cafe'
      WHEN LOWER(TRIM(r.merchant_raw))='wirral mbc' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\batp\b') THEN 'car_parking'
      WHEN LOWER(TRIM(r.merchant_raw))='wirral mbc' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'wirral\s+mbc') THEN 'council_tax'
      WHEN LOWER(TRIM(r.merchant_raw))='barbican' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'news') THEN 'convenience_store'
      WHEN LOWER(TRIM(r.merchant_raw))='barbican' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'barbican') THEN 'theatre'
      WHEN LOWER(TRIM(r.merchant_raw))='wine lodge' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'ppoint') THEN 'alcohol_beer_spirits'
      WHEN LOWER(TRIM(r.merchant_raw))='wine lodge' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'wine\s+lodge') THEN 'pub_bar'
      WHEN LOWER(TRIM(r.merchant_raw))='pier' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'fish|chips') THEN 'takeaway'
      WHEN LOWER(TRIM(r.merchant_raw))='pier' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'pieralongia') THEN 'transfer_p2p'
      WHEN LOWER(TRIM(r.merchant_raw))='pier' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'pier\s+36|donaghadee') THEN 'pub_bar'
      WHEN LOWER(TRIM(r.merchant_raw))='amber valley borough council' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'-ips|\bips\b') THEN 'car_parking'
      WHEN LOWER(TRIM(r.merchant_raw))='roadchef' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'whsmi') THEN 'convenience_store'
      WHEN LOWER(TRIM(r.merchant_raw))='wembley park' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'expre') THEN 'convenience_store'
      WHEN LOWER(TRIM(r.merchant_raw))='rbs-natwest w/end credit' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'recollection|monzo') THEN 'financial_services_other'
      WHEN r.direction='credit' AND d.leaf IN ('gambling_betting', 'gambling_casino', 'gambling_bingo', 'gambling_lottery') THEN 'gambling_unspecified'
      WHEN r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\brefund(ed)?\b') AND (d.leaf IS NULL OR d.leaf NOT IN ('gambling_betting', 'gambling_casino', 'gambling_bingo', 'gambling_lottery')) THEN 'refund_received'
      WHEN r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'returned\s+(direct\s+debit|standing\s+order)|direct\s+debit\s+reversal|\breversal of\b') THEN 'returned_payment'
      WHEN LOWER(TRIM(r.merchant_raw))='youlend' AND r.direction='credit' THEN 'loan_disbursement'
      -- T4: merchant dictionary (provider-independent, overrides both providers' own categories)
      WHEN d.leaf IS NOT NULL THEN d.leaf
      -- T5: deterministic rules
      WHEN REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '^(mr|mrs|miss|ms|dr)\\s+') THEN 'transfer_p2p'
      WHEN REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '^[a-z]\\s+[a-z]{2,}$') THEN 'transfer_p2p'
      WHEN REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), CONCAT(r'\b(', 'mum|dad|mom|nan|nana|gran|granny|grandad|sister|brother|son|daughter|wife|husband', r')\b')) THEN 'transfer_p2p'
      WHEN REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '^exchanged to (btc|eth|sol|xrp|ada|doge)') THEN 'crypto'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '(petrol|fuel)\\s*(station)?$') AND r.direction = 'debit') THEN 'fuel'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '(bingo|casino)') AND r.direction = 'debit') THEN 'gambling_unspecified'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '\\b(bet|betting|bookmaker)\\b|\\bbet\\s?\\d\\d+\\b|\\b(sky|uni|coral|lad|net|virgin|paddy|smark)bet\\b|\\bbet(fred|fair|victor|way|uk|bright)\\b') AND r.direction = 'debit') THEN 'gambling_betting'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '\\b(lottery|lotto)\\b') AND r.direction = 'debit') THEN 'gambling_lottery'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '\\b(debt (collection|recovery)|collections? ltd)\\b') AND r.direction = 'debit') THEN 'debt_collection'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), CONCAT(r'\b(', 'child maintenance', r')\b')) AND r.direction = 'credit') THEN 'income_other_unspecified'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), CONCAT(r'\b(', 'we buy any car', r')\b')) AND r.direction = 'credit') THEN 'income_other_unspecified'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), CONCAT(r'\b(', 'we buy any car', r')\b')) AND r.direction = 'debit') THEN 'vehicle_purchase'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '\\b(payday(?:\\s*loans?)?|wonga|quick\\s?quid|lending\\s?stream|118\\s*(?:118\\s*)?money|cashfloat|quid\\s?market|morses\\s?club|moneyboat|tick\\s?tock\\s*loans?|sunny\\s+loans?|cash\\s?asap|fast\\s+loan)\\b') AND r.direction = 'debit') THEN 'payday_loan'
      WHEN ((REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '\\bmorr\\b') AND NOT REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), 'petrol|pfs|fuel|caf[eé]')) AND r.direction = 'debit') THEN 'groceries'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '\\bwages\\b') AND r.direction = 'credit') THEN 'salary'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '\\boff\\s+licence\\b') AND r.direction = 'debit') THEN 'alcohol_beer_spirits'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '\\b(car park|parking)\\b') AND r.direction = 'debit') THEN 'car_parking'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '\\b(vets?|veterinary)\\b') AND r.direction = 'debit') THEN 'veterinary'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '\\b(pharmacy|chemist)\\b') AND r.direction = 'debit') THEN 'pharmacy'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bcouncil tax\\b') AND r.direction = 'debit') THEN 'council_tax'
      WHEN ((REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\b(rent|landlord)\\b') AND NOT REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), 'rent\\s*/\\s*buy|video rent|rent.?a.?car')) AND r.direction = 'debit') THEN 'rent'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\b(payday(?:\\s*loans?)?|wonga|quick\\s?quid|lending\\s?stream|118\\s*(?:118\\s*)?money|cashfloat|quid\\s?market|morses\\s?club|moneyboat|tick\\s?tock\\s*loans?|sunny\\s+loans?|cash\\s?asap|fast\\s+loan)\\b') AND r.direction = 'debit') THEN 'payday_loan'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bexpo international\\s+sup') AND r.direction = 'debit') THEN 'groceries_specialist'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bsheriff\\s+court\\b') AND r.direction = 'debit') THEN 'government_services'
      WHEN ((REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\b(universal\\s+credit|dwp\\s+uc\\b|dwp\\s+eesa|dwp\\s+pc\\b|pension\\s+credit|child\\s+benefits?|work(?:ing)?\\s+and\\s+child\\s+(?:tc|tax)|child\\s+tax\\s+credit|working\\s+tax\\s+credit|carers?\\s+allowance|disability\\s+living\\s+allowance|personal\\s+independence\\s+payment|employment\\s+and\\s+support\\s+allowance)\\b') AND NOT REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), 'debt|recovery|cms|maintenance|enforcement')) AND r.direction = 'credit') THEN 'benefits_state'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bscholastic\\s+book') AND r.direction = 'debit') THEN 'books'
      WHEN ((REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bwages\\b') AND NOT REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), 'minimum\\s+wage|living\\s+wage')) AND r.direction = 'credit') THEN 'salary'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bentertai\\b') AND r.direction = 'debit') THEN 'streaming'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), 'paypal\\s*\\*now') AND r.direction = 'debit') THEN 'streaming'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\boff\\s+licence\\b') AND r.direction = 'debit') THEN 'alcohol_beer_spirits'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bstep[\\s-]*change\\b') AND r.direction = 'debit') THEN 'debt_management_plan'
      WHEN ((REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bpaypal\\s*\\*?\\s*paypal\\s*cre|\\bpaypal\\s+credit\\b') AND NOT REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), 'payin\\s*3|pay\\s*in\\s*[34]|\\bpayin3\\b|pypl\\s*payin')) AND r.direction = 'debit') THEN 'revolving_credit_repayment'
      -- T6: provider crosswalk fallback
      WHEN x.leaf IS NOT NULL THEN x.leaf
      ELSE 'unclassified_other'
    END AS leaf,
    CASE
      WHEN r.cat='ENTERTAINMENT_CASINOS_AND_GAMBLING' AND r.direction='credit' THEN 'T1_direction'
      WHEN LOWER(TRIM(r.merchant_raw))='tesco' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\btesco bank\b') THEN 'T2_compound_tesco_bank'
      WHEN LOWER(TRIM(r.merchant_raw))='tesco' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'tescophoneins') THEN 'T2_compound_tesco_phoneins'
      WHEN LOWER(TRIM(r.merchant_raw))='tesco' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'caf[eé]') THEN 'T2_compound_tesco_cafe'
      WHEN LOWER(TRIM(r.merchant_raw)) IN ('tesco', 'one stop', 'post office', 'u.s. post office', 'asda', 'sainsbury\'s', 'co-op') AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\batm\b|\blnk\b|cash\s+at\b|cash\s+withdrawal') THEN 'T2_compound_instore_atm'
      WHEN LOWER(TRIM(r.merchant_raw)) IN ('tesco', 'one stop', 'post office', 'u.s. post office', 'asda', 'sainsbury\'s', 'co-op') AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\batm\b|cash\s+deposit') THEN 'T2_compound_instore_atm_deposit'
      WHEN LOWER(TRIM(r.merchant_raw))='tesco' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'petrol|\bpfs\b|\bfuel\b') THEN 'T2_compound_tesco_petrol'
      WHEN LOWER(TRIM(r.merchant_raw)) IN ('morr', 'cd morr') AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'caf[eé]') THEN 'T2_compound_morr_cafe'
      WHEN LOWER(TRIM(r.merchant_raw)) IN ('co-op', 'sainsbury\'s', 'asda', 'morr', 'cd morr') AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'petrol|\bpfs\b|\bfuel\b') THEN 'T2_compound_grocer_petrol'
      WHEN LOWER(TRIM(r.merchant_raw)) IN ('hmrc', 'hm revenue and customs') AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'child\s+benefits?') THEN 'T2_compound_hmrc_child_benefit'
      WHEN LOWER(TRIM(r.merchant_raw)) IN ('hmrc', 'hm revenue and customs') AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'work(?:ing)?\s+and\s+child\s+(?:tax\s+)?credits?|work(?:ing)?\s+and\s+child\s+tc\b|child\s+tax\s+credits?|working\s+tax\s+credits?') THEN 'T2_compound_hmrc_tax_credit'
      WHEN LOWER(TRIM(r.merchant_raw)) IN ('hmrc', 'hm revenue and customs') AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\bhmrc\s+sa\b|\bgov\.uk\s+sa\b|\bself[\s-]*assess') THEN 'T2_compound_hmrc_sa_refund'
      WHEN r.direction='debit' AND (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), r'\bkfc\b') OR REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\bkfc\b')) THEN 'T2_compound_kfc'
      WHEN LOWER(TRIM(r.merchant_raw))='tiktok' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'tiktok\s*shop|\bshop\s*seller') THEN 'T2_compound_tiktok_shop'
      WHEN LOWER(TRIM(r.merchant_raw))='tiktok' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'shop\s*seller') THEN 'T2_compound_tiktok_shop_seller'
      WHEN LOWER(TRIM(r.merchant_raw))='sky' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sky\s*protect|\bdgi\b.*protect|protect.*\bdgi\b') THEN 'T2_compound_sky_protect'
      WHEN LOWER(TRIM(r.merchant_raw))='child benefits' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'dwp\s*cms|dwpcms|cmsgb2012|child\s+maintenance') THEN 'T2_compound_cms_not_child_benefit'
      WHEN LOWER(TRIM(r.merchant_raw))='asda' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'asda\s*mobile') THEN 'T2_compound_asda_mobile'
      WHEN LOWER(TRIM(r.merchant_raw))='asda' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'asda\s*living') THEN 'T2_compound_asda_living'
      WHEN LOWER(TRIM(r.merchant_raw))='vodafone' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'device') THEN 'T2_compound_vodafone_device'
      WHEN LOWER(TRIM(r.merchant_raw))='amazon' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'prime\s*video') THEN 'T2_compound_amazon_prime_video'
      WHEN LOWER(TRIM(r.merchant_raw))='bolt' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'stackblitz') THEN 'T2_compound_bolt_stackblitz'
      WHEN LOWER(TRIM(r.merchant_raw))='haven holidays' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'richard\s+haven') THEN 'T2_compound_richard_haven'
      WHEN LOWER(TRIM(r.merchant_raw))='apple store' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'ingle\s+store') THEN 'T2_compound_ingle_store'
      WHEN r.direction='credit' AND (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), r'amazon\s+uk\s+services') OR REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'amazon\s+uk\s+services')) THEN 'T2_compound_amazon_uk_services_salary'
      WHEN LOWER(TRIM(r.merchant_raw))='grosvenor casino' AND r.direction='credit' AND NOT REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'returned|refund(ed)?|reversal of') THEN 'T2_compound_grosvenor_salary'
      WHEN LOWER(TRIM(r.merchant_raw))='admiral' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'casino') THEN 'T2_compound_admiral_casino'
      WHEN LOWER(TRIM(r.merchant_raw))='places for people' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'leisure|nyx|\\bleis\\b') THEN 'T2_compound_places_for_people_leisure'
      WHEN LOWER(TRIM(r.merchant_raw))='nuffield health' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'hospital|clinic|infirmar') THEN 'T2_compound_nuffield_hospital'
      WHEN LOWER(TRIM(r.merchant_raw))='ocado' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'central\\s+serv|ocado\\s+central') THEN 'T2_compound_ocado_salary'
      WHEN LOWER(TRIM(r.merchant_raw))='sodexo' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'healthcare|salary|payroll|wages') THEN 'T2_compound_sodexo_salary'
      WHEN LOWER(TRIM(r.merchant_raw))='ask italian' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'azzurri|salary|payroll|wages|\\bbgc\\b') THEN 'T2_compound_ask_italian_salary'
      WHEN LOWER(TRIM(r.merchant_raw))='fife council' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'bgc|salary|payroll|wages|faster\\s+payment|\\bfps\\b') THEN 'T2_compound_fife_council_salary'
      WHEN LOWER(TRIM(r.merchant_raw))='plum fintech' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'modulo') THEN 'T2_compound_plum_fintech_p2p'
      WHEN LOWER(TRIM(r.merchant_raw))='avon' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'[a-z]{3,}\\s+[a-z]{3,}') THEN 'T2_compound_avon_rep'
      WHEN LOWER(TRIM(r.merchant_raw))='prudential' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'annuity|pension|payout|\\bbgc\\b') THEN 'T2_compound_prudential_payout'
      WHEN LOWER(TRIM(r.merchant_raw))='fluid' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'fluid\\s+focus|\\bto\\s+[a-z]+\\s+[a-z]+') THEN 'T2_compound_fluid_p2p'
      WHEN LOWER(TRIM(r.merchant_raw))='now' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\bentertai\\b') THEN 'T2_compound_now_entertai'
      WHEN LOWER(TRIM(r.merchant_raw))='now' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'paypal') THEN 'T2_compound_now_paypal'
      WHEN LOWER(TRIM(r.merchant_raw))='paypal' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\*now\\b') THEN 'T2_compound_paypal_now'
      WHEN LOWER(TRIM(r.merchant_raw))='paypal' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'payin\\s*3|pay\\s*in\\s*[34]|\\bpayin3\\b|pypl\\s*payin') THEN 'T2_compound_paypal_payin3'
      WHEN LOWER(TRIM(r.merchant_raw))='paypal credit' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'payin\\s*3|pay\\s*in\\s*[34]|\\bpayin3\\b|pypl\\s*payin') THEN 'T2_compound_paypal_credit_payin3'
      WHEN LOWER(TRIM(r.merchant_raw))='paypal' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\*paypal\\s*cre|\\bpaypal\\s*credit\\b') THEN 'T2_compound_paypal_credit_line'
      WHEN LOWER(TRIM(r.merchant_raw))='white lion' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\bhotel\\b') THEN 'T2_compound_white_lion_hotel'
      WHEN LOWER(TRIM(r.merchant_raw))='cts' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'napa|auto\\s+parts|spares') THEN 'T2_compound_cts_napa'
      WHEN LOWER(TRIM(r.merchant_raw))='transferwise' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'via\\s+mobile') THEN 'T2_compound_transferwise_p2p'
      WHEN LOWER(TRIM(r.merchant_raw))='mercedes-benz' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'mbfin|financial') THEN 'T2_compound_mercedes_finance'
      WHEN LOWER(TRIM(r.merchant_raw))='mercedes-benz' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\bof\\s+') THEN 'T2_compound_mercedes_salary'
      WHEN LOWER(TRIM(r.merchant_raw))='mercedes-benz' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\bof\\s+|servic|\\bmot\\b') THEN 'T2_compound_mercedes_dealer'
      WHEN LOWER(TRIM(r.merchant_raw))='the kingfisher' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'convenience|grocer|\\bstore\\b') THEN 'T2_compound_kingfisher_convenience'
      WHEN LOWER(TRIM(r.merchant_raw))='gem' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'gem1|\\bcasino\\b') THEN 'T2_compound_gem_casino'
      WHEN LOWER(TRIM(r.merchant_raw))='gem' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'via\\s+mobile') THEN 'T2_compound_gem_p2p'
      WHEN LOWER(TRIM(r.merchant_raw))='cotswold outdoor' AND r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\d{6,}|salary|payroll|wages') THEN 'T2_compound_cotswold_salary'
      WHEN LOWER(TRIM(r.merchant_raw))='wood j' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'hsm|\\bholiday\\b') THEN 'T2_compound_wood_j_hsm'
      WHEN LOWER(TRIM(r.merchant_raw))='council' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'council\\s+tax') THEN 'T2_compound_council_tax_narrative'
      WHEN LOWER(TRIM(r.merchant_raw))='city' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'city\\s+airport|london\\s+city') THEN 'T2_compound_city_airport'
      WHEN LOWER(TRIM(r.merchant_raw))='city' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'city\\s+council') THEN 'T2_compound_city_council'
      WHEN LOWER(TRIM(r.merchant_raw))='home' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'etsy\\.com|homemadebouti') THEN 'T2_compound_home_etsy'
      WHEN LOWER(TRIM(r.merchant_raw))='home' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'247\\s+home\\s+rescue|home\\s+rescue') THEN 'T2_compound_home_rescue'
      WHEN LOWER(TRIM(r.merchant_raw))='home' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'online\\s+home\\s+shop') THEN 'T2_compound_home_shop'
      WHEN LOWER(TRIM(r.merchant_raw))='home' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'home\\s+glasgow|\\bglasgow\\b') THEN 'T2_compound_home_glasgow'
      WHEN LOWER(TRIM(r.merchant_raw))='orbit' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'credit\\s+services') THEN 'T2_compound_orbit_credit'
      WHEN LOWER(TRIM(r.merchant_raw))='orbit' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'allpay|south\\s+ho|housing|\\brent\\b') THEN 'T2_compound_orbit_rent'
      WHEN LOWER(TRIM(r.merchant_raw))='plus' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'plus500') THEN 'T2_compound_plus500'
      WHEN LOWER(TRIM(r.merchant_raw))='plus' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'direct\\s+debit\\s+plus|plus\\s*finance|plus\\s*loan') THEN 'T2_compound_plus_finance'
      WHEN LOWER(TRIM(r.merchant_raw))='liberty' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\\bgas\\b|electric|energy') THEN 'T2_compound_liberty_energy'
      WHEN LOWER(TRIM(r.merchant_raw))='virgin mobile' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'virgin\\s+money') THEN 'T2_compound_virgin_money_on_mobile'
      WHEN LOWER(TRIM(r.merchant_raw))='the grove' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'welwyn|chandler') THEN 'T2_compound_grove_hotel'
      WHEN LOWER(TRIM(r.merchant_raw))='cd glasgow' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sheriff\s+court') THEN 'T2_compound_cd_glasgow_sheriff'
      WHEN LOWER(TRIM(r.merchant_raw))='cd glasgow' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'glasgow\s+central') THEN 'T2_compound_cd_glasgow_central'
      WHEN LOWER(TRIM(r.merchant_raw))='cd glasgow' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'qst\s+stn') THEN 'T2_compound_cd_glasgow_qst'
      WHEN LOWER(TRIM(r.merchant_raw))='cd shop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'schiphol|let\'?s\s+play') THEN 'T2_compound_cd_shop_schiphol'
      WHEN LOWER(TRIM(r.merchant_raw))='cd shop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'khanz') THEN 'T2_compound_cd_shop_khanz'
      WHEN LOWER(TRIM(r.merchant_raw))='cd shop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'shop\s+reading') THEN 'T2_compound_cd_shop_reading'
      WHEN LOWER(TRIM(r.merchant_raw))='foot' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'firstfootsoldiers') THEN 'T2_compound_foot_firstfootsoldiers'
      WHEN LOWER(TRIM(r.merchant_raw))='foot' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'stoke\s+city\s+footbal') THEN 'T2_compound_foot_stoke'
      WHEN LOWER(TRIM(r.merchant_raw))='glossop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'valley\s+cids') THEN 'T2_compound_glossop_cids'
      WHEN LOWER(TRIM(r.merchant_raw))='glossop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'district\s*gol') THEN 'T2_compound_glossop_golf'
      WHEN LOWER(TRIM(r.merchant_raw))='glossop' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'glossop\s+sub|sumup\s*\*?\s*glossop\s+sub') THEN 'T2_compound_glossop_subway'
      WHEN LOWER(TRIM(r.merchant_raw))='crawley' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'crawley\.gov') THEN 'T2_compound_crawley_gov'
      WHEN LOWER(TRIM(r.merchant_raw))='crawley' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'black\s+belt') THEN 'T2_compound_crawley_belt'
      WHEN LOWER(TRIM(r.merchant_raw))='track' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'on\s+track|southern\s+ra') THEN 'T2_compound_track_southern'
      WHEN LOWER(TRIM(r.merchant_raw))='track' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'track\s+bandits') THEN 'T2_compound_track_bandits'
      WHEN LOWER(TRIM(r.merchant_raw))='longton' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'service\s+station') THEN 'T2_compound_longton_pfs'
      WHEN LOWER(TRIM(r.merchant_raw))='longton' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'hall\s+farm') THEN 'T2_compound_longton_farm'
      WHEN LOWER(TRIM(r.merchant_raw))='cd stirling' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'costa') THEN 'T2_compound_cd_stirling_costa'
      WHEN LOWER(TRIM(r.merchant_raw))='cd stirling' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'goosecroft') THEN 'T2_compound_cd_stirling_goosecroft'
      WHEN LOWER(TRIM(r.merchant_raw))='cd stirling' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'stirling\s+council|-ips|\bips\b') THEN 'T2_compound_cd_stirling_ips'
      WHEN LOWER(TRIM(r.merchant_raw))='royal victoria' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'infirma') THEN 'T2_compound_royal_victoria_hospital'
      WHEN LOWER(TRIM(r.merchant_raw))='royal victoria' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'country') THEN 'T2_compound_royal_victoria_park'
      WHEN LOWER(TRIM(r.merchant_raw))='cd merlin' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'cinemas?') THEN 'T2_compound_cd_merlin_cinema'
      WHEN LOWER(TRIM(r.merchant_raw))='cd merlin' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'attractions?') THEN 'T2_compound_cd_merlin_attractions'
      WHEN LOWER(TRIM(r.merchant_raw))='cd merlin' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\bderby\b') THEN 'T2_compound_cd_merlin_derby'
      WHEN LOWER(TRIM(r.merchant_raw))='cd colchester' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'leisure') THEN 'T2_compound_cd_colchester_leisure'
      WHEN LOWER(TRIM(r.merchant_raw))='cd colchester' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'borough|-ips|\bips\b') THEN 'T2_compound_cd_colchester_ips'
      WHEN LOWER(TRIM(r.merchant_raw))='cd apex' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'kart') THEN 'T2_compound_cd_apex_kart'
      WHEN LOWER(TRIM(r.merchant_raw))='cd apex' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'harlow') THEN 'T2_compound_cd_apex_harlow'
      WHEN LOWER(TRIM(r.merchant_raw))='cd con' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'coningham') THEN 'T2_compound_cd_con_arms'
      WHEN LOWER(TRIM(r.merchant_raw))='cd con' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'conniburrow') THEN 'T2_compound_cd_con_conniburrow'
      WHEN LOWER(TRIM(r.merchant_raw))='cd miss' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'whippy') THEN 'T2_compound_cd_miss_whippy'
      WHEN LOWER(TRIM(r.merchant_raw))='cd miss' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'glam|aesthetics') THEN 'T2_compound_cd_miss_beauty'
      WHEN LOWER(TRIM(r.merchant_raw))='medical' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'medical\s+aid') THEN 'T2_compound_medical_aid'
      WHEN LOWER(TRIM(r.merchant_raw))='medical' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'bill\s+medical') THEN 'T2_compound_medical_bill'
      WHEN LOWER(TRIM(r.merchant_raw))='medical' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'medical-?supermarket') THEN 'T2_compound_medical_supermarket'
      WHEN LOWER(TRIM(r.merchant_raw))='wardrobe' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'witch') THEN 'T2_compound_wardrobe_witch'
      WHEN LOWER(TRIM(r.merchant_raw))='wardrobe' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'earth\s+wardrobe') THEN 'T2_compound_wardrobe_earth'
      WHEN LOWER(TRIM(r.merchant_raw))='wardrobe' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\bwardrobe\b') THEN 'T2_compound_wardrobe_default'
      WHEN LOWER(TRIM(r.merchant_raw))='cd fresh' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'garbage') THEN 'T2_compound_cd_fresh_garbage'
      WHEN LOWER(TRIM(r.merchant_raw))='cd fresh' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'fresh\s+metro') THEN 'T2_compound_cd_fresh_metro'
      WHEN LOWER(TRIM(r.merchant_raw))='c k' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'knutsford') THEN 'T2_compound_c_k_knutsford'
      WHEN LOWER(TRIM(r.merchant_raw))='c k' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'kremlin') THEN 'T2_compound_c_k_kremlin'
      WHEN LOWER(TRIM(r.merchant_raw))='botany' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'kiosk') THEN 'T2_compound_botany_kiosk'
      WHEN LOWER(TRIM(r.merchant_raw))='botany' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'inn') THEN 'T2_compound_botany_inn'
      WHEN LOWER(TRIM(r.merchant_raw))='afc wigan wallgate' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'northern\s+trains') THEN 'T2_compound_afc_wigan_trains'
      WHEN LOWER(TRIM(r.merchant_raw))='afc wigan wallgate' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'wallgate|afc\s+wigan') THEN 'T2_compound_afc_wigan_takeaway'
      WHEN LOWER(TRIM(r.merchant_raw))='scan' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'scan\.com') THEN 'T2_compound_scan_com'
      WHEN LOWER(TRIM(r.merchant_raw))='scan' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'scandiscents') THEN 'T2_compound_scan_discents'
      WHEN LOWER(TRIM(r.merchant_raw))='mablethorpe' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'grange\s+leisure') THEN 'T2_compound_mablethorpe_grange'
      WHEN LOWER(TRIM(r.merchant_raw))='mablethorpe' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\brock\b') THEN 'T2_compound_mablethorpe_rock'
      WHEN LOWER(TRIM(r.merchant_raw))='wigmore' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'pharmacy') THEN 'T2_compound_wigmore_pharmacy'
      WHEN LOWER(TRIM(r.merchant_raw))='wigmore' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'ppoint|wigmore\s+&\s+ham|gillingham') THEN 'T2_compound_wigmore_ppoint'
      WHEN LOWER(TRIM(r.merchant_raw))='cd alder' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'vets?') THEN 'T2_compound_cd_alder_vets'
      WHEN LOWER(TRIM(r.merchant_raw))='cd alder' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'aldermaston') THEN 'T2_compound_cd_alder_aldermaston'
      WHEN LOWER(TRIM(r.merchant_raw))='cd drum' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'filling\s+station') THEN 'T2_compound_cd_drum_pfs'
      WHEN LOWER(TRIM(r.merchant_raw))='cd drum' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'drum\s+central') THEN 'T2_compound_cd_drum_central'
      WHEN LOWER(TRIM(r.merchant_raw))='c unique' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'petrol') THEN 'T2_compound_c_unique_petrol'
      WHEN LOWER(TRIM(r.merchant_raw))='c unique' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'unique\s+mobile|\bmobile\b') THEN 'T2_compound_c_unique_mobile'
      WHEN LOWER(TRIM(r.merchant_raw))='mexpress uk cd' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'medexpress|med\s*express') THEN 'T2_compound_mexpress_medexpress'
      WHEN LOWER(TRIM(r.merchant_raw))='mexpress uk cd' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'molina') THEN 'T2_compound_mexpress_molina'
      WHEN LOWER(TRIM(r.merchant_raw))='melanie and paul heweston' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'insurance') THEN 'T2_compound_heweston_insurance'
      WHEN LOWER(TRIM(r.merchant_raw))='melanie and paul heweston' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\bloan\b') THEN 'T2_compound_heweston_loan'
      WHEN LOWER(TRIM(r.merchant_raw))='wik' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'maciagowska|repayment') THEN 'T2_compound_wik_repayment'
      WHEN LOWER(TRIM(r.merchant_raw))='wik' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sopel') THEN 'T2_compound_wik_sopel'
      WHEN LOWER(TRIM(r.merchant_raw))='artbox' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'scoop') THEN 'T2_compound_artbox_scoop'
      WHEN LOWER(TRIM(r.merchant_raw))='artbox' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'artbox') THEN 'T2_compound_artbox_shop'
      WHEN LOWER(TRIM(r.merchant_raw))='cd best' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'best4vapes|best\s*4\s*vapes') THEN 'T2_compound_cd_best_vapes'
      WHEN LOWER(TRIM(r.merchant_raw))='cd best' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'best\s+one') THEN 'T2_compound_cd_best_one'
      WHEN LOWER(TRIM(r.merchant_raw))='fitzsimons' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'joshua') THEN 'T2_compound_fitzsimons_joshua'
      WHEN LOWER(TRIM(r.merchant_raw))='fitzsimons' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'fitzsimons') THEN 'T2_compound_fitzsimons_pub'
      WHEN LOWER(TRIM(r.merchant_raw))='banquet' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'paypal') THEN 'T2_compound_banquet_paypal'
      WHEN LOWER(TRIM(r.merchant_raw))='banquet' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sq\s*\*|nottingham') THEN 'T2_compound_banquet_sq'
      WHEN LOWER(TRIM(r.merchant_raw))='thurrock' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'community') THEN 'T2_compound_thurrock_community'
      WHEN LOWER(TRIM(r.merchant_raw))='thurrock' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'borough|-ips') THEN 'T2_compound_thurrock_ips'
      WHEN LOWER(TRIM(r.merchant_raw))='derek' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'wright|loan\s+repayment') THEN 'T2_compound_derek_wright'
      WHEN LOWER(TRIM(r.merchant_raw))='derek' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'derek\s+jones|\bjones\b') THEN 'T2_compound_derek_jones'
      WHEN LOWER(TRIM(r.merchant_raw))='the black' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'black\s+country') THEN 'T2_compound_the_black_chip'
      WHEN LOWER(TRIM(r.merchant_raw))='the black' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'blackheath') THEN 'T2_compound_the_black_heath'
      WHEN LOWER(TRIM(r.merchant_raw))='east bridgford' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'gdn|garden') THEN 'T2_compound_east_bridgford_garden'
      WHEN LOWER(TRIM(r.merchant_raw))='east bridgford' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'medica') THEN 'T2_compound_east_bridgford_medical'
      WHEN LOWER(TRIM(r.merchant_raw))='cd tp' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'amity|kebabs?') THEN 'T2_compound_cd_tp_kebabs'
      WHEN LOWER(TRIM(r.merchant_raw))='cd tp' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'b\s+and\s+j') THEN 'T2_compound_cd_tp_bandj'
      WHEN LOWER(TRIM(r.merchant_raw))='cd no.' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'off\s+licence') THEN 'T2_compound_cd_no_offlicence'
      WHEN LOWER(TRIM(r.merchant_raw))='cd no.' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'no\.?\s*7\s+restaurant|restaurant') THEN 'T2_compound_cd_no_restaurant'
      WHEN LOWER(TRIM(r.merchant_raw))='cd sheffield' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'chaucer') THEN 'T2_compound_cd_sheffield_chaucer'
      WHEN LOWER(TRIM(r.merchant_raw))='cd sheffield' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'meadow') THEN 'T2_compound_cd_sheffield_meadowhall'
      WHEN LOWER(TRIM(r.merchant_raw))='cd green' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'green\s+man') THEN 'T2_compound_cd_green_man'
      WHEN LOWER(TRIM(r.merchant_raw))='cd green' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'green\s+valley') THEN 'T2_compound_cd_green_valley'
      WHEN LOWER(TRIM(r.merchant_raw))='egg' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'zettle|eggbugland') THEN 'T2_compound_egg_zettle'
      WHEN LOWER(TRIM(r.merchant_raw))='egg' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'162224|direct\s+debit|\begg\b') THEN 'T2_compound_egg_energy'
      WHEN LOWER(TRIM(r.merchant_raw))='jasmine' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'restaurant') THEN 'T2_compound_jasmine_restaurant'
      WHEN LOWER(TRIM(r.merchant_raw))='jasmine' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'chesney|sortcode|\d{10,}') THEN 'T2_compound_jasmine_p2p'
      WHEN LOWER(TRIM(r.merchant_raw))='paymy.vet' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'groom') THEN 'T2_compound_paymyvet_groom'
      WHEN LOWER(TRIM(r.merchant_raw))='paymy.vet' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'vets?|bolton') THEN 'T2_compound_paymyvet_vets'
      WHEN LOWER(TRIM(r.merchant_raw))='bill\'s' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'nanny') THEN 'T2_compound_bills_nanny'
      WHEN LOWER(TRIM(r.merchant_raw))='bill\'s' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'mcgill|buses') THEN 'T2_compound_bills_bus'
      WHEN LOWER(TRIM(r.merchant_raw))='bill\'s' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'restaurant') THEN 'T2_compound_bills_restaurant'
      WHEN LOWER(TRIM(r.merchant_raw))='reddish' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'service\s+stati') THEN 'T2_compound_reddish_pfs'
      WHEN LOWER(TRIM(r.merchant_raw))='reddish' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'convenience') THEN 'T2_compound_reddish_shop'
      WHEN LOWER(TRIM(r.merchant_raw))='hafod' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sq\s*\*') THEN 'T2_compound_hafod_sq'
      WHEN LOWER(TRIM(r.merchant_raw))='hafod' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'housing') THEN 'T2_compound_hafod_housing'
      WHEN LOWER(TRIM(r.merchant_raw))='hart' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'hart\s+il|sortcode') THEN 'T2_compound_hart_il'
      WHEN LOWER(TRIM(r.merchant_raw))='hart' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'district\s+council|\bcouncil\b') THEN 'T2_compound_hart_council'
      WHEN LOWER(TRIM(r.merchant_raw))='blackwell\'s' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sammy|k\s+a\s+blackwell') THEN 'T2_compound_blackwells_p2p'
      WHEN LOWER(TRIM(r.merchant_raw))='blackwell\'s' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'blackwell') THEN 'T2_compound_blackwells_books'
      WHEN LOWER(TRIM(r.merchant_raw))='gamesys operation' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'gamesys') THEN 'T2_compound_gamesys_unspecified'
      WHEN LOWER(TRIM(r.merchant_raw))='the ups store' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'ppoint|g\s+and\s+s\s+stores') THEN 'T2_compound_ups_ppoint'
      WHEN LOWER(TRIM(r.merchant_raw))='the ups store' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'ups\s+store') THEN 'T2_compound_ups_store'
      WHEN LOWER(TRIM(r.merchant_raw))='hiba' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'bibs|bakri|clothing') THEN 'T2_compound_hiba_bibs'
      WHEN LOWER(TRIM(r.merchant_raw))='hiba' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'sagheer') THEN 'T2_compound_hiba_sagheer'
      WHEN LOWER(TRIM(r.merchant_raw))='collection pot' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'collection\s+pot') THEN 'T2_compound_collection_pot_dining'
      WHEN LOWER(TRIM(r.merchant_raw))='wirral mbc' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\batp\b') THEN 'T2_compound_wirral_atp'
      WHEN LOWER(TRIM(r.merchant_raw))='wirral mbc' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'wirral\s+mbc') THEN 'T2_compound_wirral_council'
      WHEN LOWER(TRIM(r.merchant_raw))='barbican' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'news') THEN 'T2_compound_barbican_news'
      WHEN LOWER(TRIM(r.merchant_raw))='barbican' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'barbican') THEN 'T2_compound_barbican_theatre'
      WHEN LOWER(TRIM(r.merchant_raw))='wine lodge' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'ppoint') THEN 'T2_compound_wine_lodge_ppoint'
      WHEN LOWER(TRIM(r.merchant_raw))='wine lodge' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'wine\s+lodge') THEN 'T2_compound_wine_lodge_pub'
      WHEN LOWER(TRIM(r.merchant_raw))='pier' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'fish|chips') THEN 'T2_compound_pier_chips'
      WHEN LOWER(TRIM(r.merchant_raw))='pier' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'pieralongia') THEN 'T2_compound_pier_p2p'
      WHEN LOWER(TRIM(r.merchant_raw))='pier' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'pier\s+36|donaghadee') THEN 'T2_compound_pier_36'
      WHEN LOWER(TRIM(r.merchant_raw))='amber valley borough council' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'-ips|\bips\b') THEN 'T2_compound_amber_valley_ips'
      WHEN LOWER(TRIM(r.merchant_raw))='roadchef' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'whsmi') THEN 'T2_compound_roadchef_whsmith'
      WHEN LOWER(TRIM(r.merchant_raw))='wembley park' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'expre') THEN 'T2_compound_wembley_park_express'
      WHEN LOWER(TRIM(r.merchant_raw))='rbs-natwest w/end credit' AND r.direction='debit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'recollection|monzo') THEN 'T2_compound_natwest_westend_recollection'
      WHEN r.direction='credit' AND d.leaf IN ('gambling_betting', 'gambling_casino', 'gambling_bingo', 'gambling_lottery') THEN 'T1_direction_gambling_credit'
      WHEN r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'\brefund(ed)?\b') AND (d.leaf IS NULL OR d.leaf NOT IN ('gambling_betting', 'gambling_casino', 'gambling_bingo', 'gambling_lottery')) THEN 'T2_compound_refund'
      WHEN r.direction='credit' AND REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), r'returned\s+(direct\s+debit|standing\s+order)|direct\s+debit\s+reversal|\breversal of\b') THEN 'T2_compound_returned_payment'
      WHEN LOWER(TRIM(r.merchant_raw))='youlend' AND r.direction='credit' THEN 'T2_compound_youlend_disbursement'
      WHEN d.leaf IS NOT NULL THEN 'T4_merchant_dictionary'
      WHEN REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '^(mr|mrs|miss|ms|dr)\\s+') THEN 'T5_rule_R01'
      WHEN REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '^[a-z]\\s+[a-z]{2,}$') THEN 'T5_rule_R02'
      WHEN REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), CONCAT(r'\b(', 'mum|dad|mom|nan|nana|gran|granny|grandad|sister|brother|son|daughter|wife|husband', r')\b')) THEN 'T5_rule_R03'
      WHEN REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '^exchanged to (btc|eth|sol|xrp|ada|doge)') THEN 'T5_rule_R04'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '(petrol|fuel)\\s*(station)?$') AND r.direction = 'debit') THEN 'T5_rule_R05'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '(bingo|casino)') AND r.direction = 'debit') THEN 'T5_rule_R06'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '\\b(bet|betting|bookmaker)\\b|\\bbet\\s?\\d\\d+\\b|\\b(sky|uni|coral|lad|net|virgin|paddy|smark)bet\\b|\\bbet(fred|fair|victor|way|uk|bright)\\b') AND r.direction = 'debit') THEN 'T5_rule_R07'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '\\b(lottery|lotto)\\b') AND r.direction = 'debit') THEN 'T5_rule_R08'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '\\b(debt (collection|recovery)|collections? ltd)\\b') AND r.direction = 'debit') THEN 'T5_rule_R14'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), CONCAT(r'\b(', 'child maintenance', r')\b')) AND r.direction = 'credit') THEN 'T5_rule_R15'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), CONCAT(r'\b(', 'we buy any car', r')\b')) AND r.direction = 'credit') THEN 'T5_rule_R16'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), CONCAT(r'\b(', 'we buy any car', r')\b')) AND r.direction = 'debit') THEN 'T5_rule_R17'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '\\b(payday(?:\\s*loans?)?|wonga|quick\\s?quid|lending\\s?stream|118\\s*(?:118\\s*)?money|cashfloat|quid\\s?market|morses\\s?club|moneyboat|tick\\s?tock\\s*loans?|sunny\\s+loans?|cash\\s?asap|fast\\s+loan)\\b') AND r.direction = 'debit') THEN 'T5_rule_R18'
      WHEN ((REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '\\bmorr\\b') AND NOT REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), 'petrol|pfs|fuel|caf[eé]')) AND r.direction = 'debit') THEN 'T5_rule_R21'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '\\bwages\\b') AND r.direction = 'credit') THEN 'T5_rule_R26'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '\\boff\\s+licence\\b') AND r.direction = 'debit') THEN 'T5_rule_R30'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '\\b(car park|parking)\\b') AND r.direction = 'debit') THEN 'T5_rule_R09'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '\\b(vets?|veterinary)\\b') AND r.direction = 'debit') THEN 'T5_rule_R10'
      WHEN (REGEXP_CONTAINS(LOWER(TRIM(r.merchant_raw)), '\\b(pharmacy|chemist)\\b') AND r.direction = 'debit') THEN 'T5_rule_R11'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bcouncil tax\\b') AND r.direction = 'debit') THEN 'T5_rule_R12'
      WHEN ((REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\b(rent|landlord)\\b') AND NOT REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), 'rent\\s*/\\s*buy|video rent|rent.?a.?car')) AND r.direction = 'debit') THEN 'T5_rule_R13'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\b(payday(?:\\s*loans?)?|wonga|quick\\s?quid|lending\\s?stream|118\\s*(?:118\\s*)?money|cashfloat|quid\\s?market|morses\\s?club|moneyboat|tick\\s?tock\\s*loans?|sunny\\s+loans?|cash\\s?asap|fast\\s+loan)\\b') AND r.direction = 'debit') THEN 'T5_rule_R19'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bexpo international\\s+sup') AND r.direction = 'debit') THEN 'T5_rule_R20'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bsheriff\\s+court\\b') AND r.direction = 'debit') THEN 'T5_rule_R22'
      WHEN ((REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\b(universal\\s+credit|dwp\\s+uc\\b|dwp\\s+eesa|dwp\\s+pc\\b|pension\\s+credit|child\\s+benefits?|work(?:ing)?\\s+and\\s+child\\s+(?:tc|tax)|child\\s+tax\\s+credit|working\\s+tax\\s+credit|carers?\\s+allowance|disability\\s+living\\s+allowance|personal\\s+independence\\s+payment|employment\\s+and\\s+support\\s+allowance)\\b') AND NOT REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), 'debt|recovery|cms|maintenance|enforcement')) AND r.direction = 'credit') THEN 'T5_rule_R23'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bscholastic\\s+book') AND r.direction = 'debit') THEN 'T5_rule_R24'
      WHEN ((REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bwages\\b') AND NOT REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), 'minimum\\s+wage|living\\s+wage')) AND r.direction = 'credit') THEN 'T5_rule_R25'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bentertai\\b') AND r.direction = 'debit') THEN 'T5_rule_R27'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), 'paypal\\s*\\*now') AND r.direction = 'debit') THEN 'T5_rule_R28'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\boff\\s+licence\\b') AND r.direction = 'debit') THEN 'T5_rule_R29'
      WHEN (REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bstep[\\s-]*change\\b') AND r.direction = 'debit') THEN 'T5_rule_R31'
      WHEN ((REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), '\\bpaypal\\s*\\*?\\s*paypal\\s*cre|\\bpaypal\\s+credit\\b') AND NOT REGEXP_CONTAINS(LOWER(COALESCE(r.description_raw, '')), 'payin\\s*3|pay\\s*in\\s*[34]|\\bpayin3\\b|pypl\\s*payin')) AND r.direction = 'debit') THEN 'T5_rule_R32'
      WHEN x.leaf IS NOT NULL THEN 'T6_provider_crosswalk'
      ELSE 'T7_unclassified'
    END AS resolution_tier
  FROM plaid_raw r
  LEFT JOIN plaid_xw x ON r.cat = x.plaid_cat
  LEFT JOIN dict_xw d ON LOWER(TRIM(r.merchant_raw)) = d.merchant
),

combined AS (
  SELECT 'equifax' AS provider, leaf, resolution_tier FROM eqx_resolved
  UNION ALL
  SELECT 'plaid', leaf, resolution_tier FROM plaid_resolved
)
SELECT
  c.provider, c.resolution_tier,
  COUNT(*) AS n,
  ROUND(100*COUNT(*)/SUM(COUNT(*)) OVER (PARTITION BY c.provider),2) AS pct_of_provider,
  COUNT(DISTINCT c.leaf) AS distinct_leaves,
  COUNTIF(m.leaf IS NULL) AS leaves_missing_metadata
FROM combined c
LEFT JOIN leaf_meta m ON c.leaf = m.leaf
GROUP BY 1,2 ORDER BY 1, n DESC
