
/*Data transfered today*/
barChart("#plot_data_today", 800, 300, "Transferred data", "Time", "Data [kB]",
         "/rest/statistics/data_per_day",
         '{"day": 1, "month":4, "year":2013}');

/*Number files transfered today*/
barChart("#plot_number_files_today", 800, 300, "Transferred files", "Time", "Number",
         "/rest/statistics/number_files_per_day",
         '{"day": 1, "month":4, "year":2013}');
