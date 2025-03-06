-- SQLite
select * from old_surveys where success = 0;
select * from old_surveys where success = 1;
select count(*) from old_surveys where success = 1;
select count(*) from old_surveys where success = 0;