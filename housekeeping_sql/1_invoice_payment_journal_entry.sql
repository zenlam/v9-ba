-- step 1. Remove first all other account move and move line which are not of invoice and payment. 

delete from account_move where id not in (select id from account_move where id in 
(
	select move_id from account_invoice) 
	union
	select move_id from account_move_line where payment_id is not null
)

--- step : 2
-- To delete all invoice older then date "2018-04-30"
select id from account_invoice where date_invoice <= '2018-04-30'
-- Keep this all INVOICE id (in separate file as we need this later on to delete invoice)

--- step : 3
select move_id from account_invoice where date_invoice <= '2018-04-30'
-- VERY IMPORTANT keep two list of id 

-- Keep this all MOVE id (in separate file as we need this later on to delete move)

--- step : 4
delete from account_invoice where date_invoice <= '2018-04-30'

--- step : 5
delete from account_move where id in (list of move id of invoice from file)
-- if above query raise constrain then 

--- step : 6
select id from account_move_line where move_id in (list of move id of invoice from file)
-- Keep this all MOVE LINE ID (in separate file as we need this later on to check payment for this)

--- step : 7
select id from account_partial_reconcile 
where debit_move_id in (list of MOVE LINE ID from file) 
or credit_move_id in (list of MOVE LINE ID from file)

--- step : 8
delete from account_partial_reconcile 
where debit_move_id in (list of MOVE LINE ID from file) 
or credit_move_id in (list of MOVE LINE ID from file)

* RUN Again Step 5


--- step 9 for payment older then 30/apr

--select id from account_payment where payment_date <= '2018-04-30'
--keep this all payment id in file

--- step 10
--select move_id from account_move_line where payment_id in (1,12,2,3,4,6,7,9,8,10,11)
--keep payment move id in file

--- step 11
--delete from account_move where id in (44032543,44032543,44032548,44032545,44032545,44032554,44032556,44032644,44032644,44032554,44032640,44032640,44032548,44032538,44032538,44032540,44032540,44032556,44032566,44032566,44032593,44032593)

--- step 12
--delete from account_payment where payment_date <= '2018-04-30'












