- Import
- 21Databases

# 21Databases


## 21.1Introduction


A huge amount of data lives in databases, so it’s essential that you know how to access it. Sometimes you can ask someone to download a snapshot into a.csvfor you, but this gets painful quickly: every time you need to make a change you’ll have to communicate with another human. You want to be able to reach into the database directly to get the data you need, when you need it.


In this chapter, you’ll first learn the basics of the DBI package: how to use it to connect to a database and then retrieve data with a SQL1query.SQL, short forstructuredquerylanguage, is the lingua franca of databases, and is an important language for all data scientists to learn. That said, we’re not going to start with SQL, but instead we’ll teach you dbplyr, which can translate your dplyr code to the SQL. We’ll use that as a way to teach you some of the most important features of SQL. You won’t become a SQL master by the end of the chapter, but you will be able to identify the most important components and understand what they do.


### 21.1.1Prerequisites


In this chapter, we’ll introduce DBI and dbplyr. DBI is a low-level interface that connects to databases and executes SQL; dbplyr is a high-level interface that translates your dplyr code to SQL queries then executes them with DBI.


```
library(DBI)
library(dbplyr)
library(tidyverse)
```


## 21.2Database basics


At the simplest level, you can think about a database as a collection of data frames, calledtablesin database terminology. Like a data frame, a database table is a collection of named columns, where every value in the column is the same type. There are three high level differences between data frames and database tables:

- Database tables are stored on disk and can be arbitrarily large. Data frames are stored in memory, and are fundamentally limited (although that limit is still plenty large for many problems).

Database tables are stored on disk and can be arbitrarily large. Data frames are stored in memory, and are fundamentally limited (although that limit is still plenty large for many problems).

- Database tables almost always have indexes. Much like the index of a book, a database index makes it possible to quickly find rows of interest without having to look at every single row. Data frames and tibbles don’t have indexes, but data.tables do, which is one of the reasons that they’re so fast.

Database tables almost always have indexes. Much like the index of a book, a database index makes it possible to quickly find rows of interest without having to look at every single row. Data frames and tibbles don’t have indexes, but data.tables do, which is one of the reasons that they’re so fast.

- Most classical databases are optimized for rapidly collecting data, not analyzing existing data. These databases are calledrow-orientedbecause the data is stored row-by-row, rather than column-by-column like R. More recently, there’s been much development ofcolumn-orienteddatabases that make analyzing the existing data much faster.

Most classical databases are optimized for rapidly collecting data, not analyzing existing data. These databases are calledrow-orientedbecause the data is stored row-by-row, rather than column-by-column like R. More recently, there’s been much development ofcolumn-orienteddatabases that make analyzing the existing data much faster.


Databases are run by database management systems (DBMS’s for short), which come in three basic forms:

- Client-serverDBMS’s run on a powerful central server, which you connect to from your computer (the client). They are great for sharing data with multiple people in an organization. Popular client-server DBMS’s include PostgreSQL, MariaDB, SQL Server, and Oracle.
- CloudDBMS’s, like Snowflake, Amazon’s RedShift, and Google’s BigQuery, are similar to client server DBMS’s, but they run in the cloud. This means that they can easily handle extremely large datasets and can automatically provide more compute resources as needed.
- In-processDBMS’s, like SQLite or duckdb, run entirely on your computer. They’re great for working with large datasets where you’re the primary user.

## 21.3Connecting to a database


To connect to the database from R, you’ll use a pair of packages:

- You’ll always use DBI (databaseinterface) because it provides a set of generic functions that connect to the database, upload data, run SQL queries, etc.

You’ll always use DBI (databaseinterface) because it provides a set of generic functions that connect to the database, upload data, run SQL queries, etc.

- You’ll also use a package tailored for the DBMS you’re connecting to. This package translates the generic DBI commands into the specifics needed for a given DBMS. There’s usually one package for each DBMS, e.g. RPostgres for PostgreSQL and RMariaDB for MySQL.

You’ll also use a package tailored for the DBMS you’re connecting to. This package translates the generic DBI commands into the specifics needed for a given DBMS. There’s usually one package for each DBMS, e.g. RPostgres for PostgreSQL and RMariaDB for MySQL.


If you can’t find a specific package for your DBMS, you can usually use the odbc package instead. This uses the ODBC protocol supported by many DBMS. odbc requires a little more setup because you’ll also need to install an ODBC driver and tell the odbc package where to find it.


Concretely, you create a database connection usingDBI::dbConnect(). The first argument selects the DBMS2, then the second and subsequent arguments describe how to connect to it (i.e. where it lives and the credentials that you need to access it). The following code shows a couple of typical examples:


```
con <- DBI::dbConnect(
  RMariaDB::MariaDB(), 
  username = "foo"
)
con <- DBI::dbConnect(
  RPostgres::Postgres(), 
  hostname = "databases.mycompany.com", 
  port = 1234
)
```


The precise details of the connection vary a lot from DBMS to DBMS so unfortunately we can’t cover all the details here. This means you’ll need to do a little research on your own. Typically you can ask the other data scientists in your team or talk to your DBA (databaseadministrator). The initial setup will often take a little fiddling (and maybe some googling) to get it right, but you’ll generally only need to do it once.


### 21.3.1In this book


Setting up a client-server or cloud DBMS would be a pain for this book, so we’ll instead use an in-process DBMS that lives entirely in an R package: duckdb. Thanks to the magic of DBI, the only difference between using duckdb and any other DBMS is how you’ll connect to the database. This makes it great to teach with because you can easily run this code as well as easily take what you learn and apply it elsewhere.


Connecting to duckdb is particularly simple because the defaults create a temporary database that is deleted when you quit R. That’s great for learning because it guarantees that you’ll start from a clean slate every time you restart R:


```
con <- DBI::dbConnect(duckdb::duckdb())
```


duckdb is a high-performance database that’s designed very much for the needs of a data scientist. We use it here because it’s very easy to get started with, but it’s also capable of handling gigabytes of data with great speed. If you want to use duckdb for a real data analysis project, you’ll also need to supply thedbdirargument to make a persistent database and tell duckdb where to save it. Assuming you’re using a project (Chapter 6), it’s reasonable to store it in theduckdbdirectory of the current project:


```
con <- DBI::dbConnect(duckdb::duckdb(), dbdir = "duckdb")
```


### 21.3.2Load some data


Since this is a new database, we need to start by adding some data. Here we’ll addmpganddiamondsdatasets from ggplot2 usingDBI::dbWriteTable(). The simplest usage ofdbWriteTable()needs three arguments: a database connection, the name of the table to create in the database, and a data frame of data.


```
dbWriteTable(con, "mpg", ggplot2::mpg)
dbWriteTable(con, "diamonds", ggplot2::diamonds)
```


If you’re using duckdb in a real project, we highly recommend learning aboutduckdb_read_csv()andduckdb_register_arrow(). These give you powerful and performant ways to quickly load data directly into duckdb, without having to first load it into R. We’ll also show off a useful technique for loading multiple files into a database inSection 26.4.1.


### 21.3.3DBI basics


You can check that the data is loaded correctly by using a couple of other DBI functions:dbListTables()lists all tables in the database3anddbReadTable()retrieves the contents of a table.


```
dbListTables(con)
#> [1] "diamonds" "mpg"

con |> 
  dbReadTable("diamonds") |> 
  as_tibble()
#> # A tibble: 53,940 × 10
#>   carat cut       color clarity depth table price     x     y     z
#>   <dbl> <fct>     <fct> <fct>   <dbl> <dbl> <int> <dbl> <dbl> <dbl>
#> 1  0.23 Ideal     E     SI2      61.5    55   326  3.95  3.98  2.43
#> 2  0.21 Premium   E     SI1      59.8    61   326  3.89  3.84  2.31
#> 3  0.23 Good      E     VS1      56.9    65   327  4.05  4.07  2.31
#> 4  0.29 Premium   I     VS2      62.4    58   334  4.2   4.23  2.63
#> 5  0.31 Good      J     SI2      63.3    58   335  4.34  4.35  2.75
#> 6  0.24 Very Good J     VVS2     62.8    57   336  3.94  3.96  2.48
#> # ℹ 53,934 more rows
```


dbReadTable()returns adata.frameso we useas_tibble()to convert it into a tibble so that it prints nicely.


If you already know SQL, you can usedbGetQuery()to get the results of running a query on the database:


```
sql <- "
  SELECT carat, cut, clarity, color, price 
  FROM diamonds 
  WHERE price > 15000
"
as_tibble(dbGetQuery(con, sql))
#> # A tibble: 1,655 × 5
#>   carat cut       clarity color price
#>   <dbl> <fct>     <fct>   <fct> <int>
#> 1  1.54 Premium   VS2     E     15002
#> 2  1.19 Ideal     VVS1    F     15005
#> 3  2.1  Premium   SI1     I     15007
#> 4  1.69 Ideal     SI1     D     15011
#> 5  1.5  Very Good VVS2    G     15013
#> 6  1.73 Very Good VS1     G     15014
#> # ℹ 1,649 more rows
```


If you’ve never seen SQL before, don’t worry! You’ll learn more about it shortly. But if you read it carefully, you might guess that it selects five columns of the diamonds dataset and all the rows wherepriceis greater than 15,000.


## 21.4dbplyr basics


Now that we’ve connected to a database and loaded up some data, we can start to learn about dbplyr. dbplyr is a dplyrbackend, which means that you keep writing dplyr code but the backend executes it differently. In this, dbplyr translates to SQL; other backends includedtplyrwhich translates todata.table, andmultidplyrwhich executes your code on multiple cores.


To use dbplyr, you must first usetbl()to create an object that represents a database table:


```
diamonds_db <- tbl(con, "diamonds")
diamonds_db
#> # Source:   table<diamonds> [?? x 10]
#> # Database: DuckDB 1.5.2 [unknown@Linux 6.17.0-1013-azure:R 4.6.0/:memory:]
#>   carat cut       color clarity depth table price     x     y     z
#>   <dbl> <fct>     <fct> <fct>   <dbl> <dbl> <int> <dbl> <dbl> <dbl>
#> 1  0.23 Ideal     E     SI2      61.5    55   326  3.95  3.98  2.43
#> 2  0.21 Premium   E     SI1      59.8    61   326  3.89  3.84  2.31
#> 3  0.23 Good      E     VS1      56.9    65   327  4.05  4.07  2.31
#> 4  0.29 Premium   I     VS2      62.4    58   334  4.2   4.23  2.63
#> 5  0.31 Good      J     SI2      63.3    58   335  4.34  4.35  2.75
#> 6  0.24 Very Good J     VVS2     62.8    57   336  3.94  3.96  2.48
#> # ℹ more rows
```


There are two other common ways to interact with a database. First, many corporate databases are very large so you need some hierarchy to keep all the tables organized. In that case you might need to supply a schema, or a catalog and a schema, in order to pick the table you’re interested in:


```
diamonds_db <- tbl(con, in_schema("sales", "diamonds"))
diamonds_db <- tbl(con, in_catalog("north_america", "sales", "diamonds"))
```


Other times you might want to use your own SQL query as a starting point:


```
diamonds_db <- tbl(con, sql("SELECT * FROM diamonds"))
```


This object islazy; when you use dplyr verbs on it, dplyr doesn’t do any work: it just records the sequence of operations that you want to perform and only performs them when needed. For example, take the following pipeline:


```
big_diamonds_db <- diamonds_db |> 
  filter(price > 15000) |> 
  select(carat:clarity, price)

big_diamonds_db
#> # Source:   SQL [?? x 5]
#> # Database: DuckDB 1.5.2 [unknown@Linux 6.17.0-1013-azure:R 4.6.0/:memory:]
#>   carat cut       color clarity price
#>   <dbl> <fct>     <fct> <fct>   <int>
#> 1  1.54 Premium   E     VS2     15002
#> 2  1.19 Ideal     F     VVS1    15005
#> 3  2.1  Premium   I     SI1     15007
#> 4  1.69 Ideal     D     SI1     15011
#> 5  1.5  Very Good G     VVS2    15013
#> 6  1.73 Very Good G     VS1     15014
#> # ℹ more rows
```


You can tell this object represents a database query because it prints the DBMS name at the top, and while it tells you the number of columns, it typically doesn’t know the number of rows. This is because finding the total number of rows usually requires executing the complete query, something we’re trying to avoid.


You can see the SQL code generated by the dplyr functionshow_query(). If you know dplyr, this is a great way to learn SQL! Write some dplyr code, get dbplyr to translate it to SQL, and then try to figure out how the two languages match up.


```
big_diamonds_db |>
  show_query()
#> <SQL>
#> SELECT carat, cut, color, clarity, price
#> FROM diamonds
#> WHERE (price > 15000.0)
```


To get all the data back into R, you callcollect(). Behind the scenes, this generates the SQL, callsdbGetQuery()to get the data, then turns the result into a tibble:


```
big_diamonds <- big_diamonds_db |> 
  collect()
big_diamonds
#> # A tibble: 1,655 × 5
#>   carat cut       color clarity price
#>   <dbl> <fct>     <fct> <fct>   <int>
#> 1  1.54 Premium   E     VS2     15002
#> 2  1.19 Ideal     F     VVS1    15005
#> 3  2.1  Premium   I     SI1     15007
#> 4  1.69 Ideal     D     SI1     15011
#> 5  1.5  Very Good G     VVS2    15013
#> 6  1.73 Very Good G     VS1     15014
#> # ℹ 1,649 more rows
```


Typically, you’ll use dbplyr to select the data you want from the database, performing basic filtering and aggregation using the translations described below. Then, once you’re ready to analyse the data with functions that are unique to R, you’llcollect()the data to get an in-memory tibble, and continue your work with pure R code.


## 21.5SQL


The rest of the chapter will teach you a little SQL through the lens of dbplyr. It’s a rather non-traditional introduction to SQL but we hope it will get you quickly up to speed with the basics. Luckily, if you understand dplyr you’re in a great place to quickly pick up SQL because so many of the concepts are the same.


We’ll explore the relationship between dplyr and SQL using a couple of old friends from the nycflights13 package:flightsandplanes. These datasets are easy to get into our learning database because dbplyr comes with a function that copies the tables from nycflights13 to our database:


```
dbplyr::copy_nycflights13(con)
#> Creating table: airlines
#> Creating table: airports
#> Creating table: flights
#> Creating table: planes
#> Creating table: weather
flights <- tbl(con, "flights")
planes <- tbl(con, "planes")
```


### 21.5.1SQL basics


The top-level components of SQL are calledstatements. Common statements includeCREATEfor defining new tables,INSERTfor adding data, andSELECTfor retrieving data. We will focus onSELECTstatements, also calledqueries, because they are almost exclusively what you’ll use as a data scientist.


A query is made up ofclauses. There are five important clauses:SELECT,FROM,WHERE,ORDER BY, andGROUP BY. Every query must have theSELECT4andFROM5clauses and the simplest query isSELECT * FROM table, which selects all columns from the specified table . This is what dbplyr generates for an unadulterated table :


```
flights |> show_query()
#> <SQL>
#> SELECT *
#> FROM flights
planes |> show_query()
#> <SQL>
#> SELECT *
#> FROM planes
```


WHEREandORDER BYcontrol which rows are included and how they are ordered:


```
flights |> 
  filter(dest == "IAH") |> 
  arrange(dep_delay) |>
  show_query()
#> <SQL>
#> SELECT flights.*
#> FROM flights
#> WHERE (dest = 'IAH')
#> ORDER BY dep_delay
```


GROUP BYconverts the query to a summary, causing aggregation to happen:


```
flights |> 
  group_by(dest) |> 
  summarize(dep_delay = mean(dep_delay, na.rm = TRUE)) |> 
  show_query()
#> <SQL>
#> SELECT dest, AVG(dep_delay) AS dep_delay
#> FROM flights
#> GROUP BY dest
```


There are two important differences between dplyr verbs and SELECT clauses:

- In SQL, case doesn’t matter: you can writeselect,SELECT, or evenSeLeCt. In this book we’ll stick with the common convention of writing SQL keywords in uppercase to distinguish them from table or variables names.
- In SQL, order matters: you must always write the clauses in the orderSELECT,FROM,WHERE,GROUP BY,ORDER BY. Confusingly, this order doesn’t match how the clauses are actually evaluated which is firstFROM, thenWHERE,GROUP BY,SELECT, andORDER BY.

The following sections explore each clause in more detail.


Note that while SQL is a standard, it is extremely complex and no database follows it exactly. While the main components that we’ll focus on in this book are very similar between DBMS’s, there are many minor variations. Fortunately, dbplyr is designed to handle this problem and generates different translations for different databases. It’s not perfect, but it’s continually improving, and if you hit a problem you can file an issueon GitHubto help us do better.


### 21.5.2SELECT


TheSELECTclause is the workhorse of queries and performs the same job asselect(),mutate(),rename(),relocate(), and, as you’ll learn in the next section,summarize().


select(),rename(), andrelocate()have very direct translations toSELECTas they just affect where a column appears (if at all) along with its name:


```
planes |> 
  select(tailnum, type, manufacturer, model, year) |> 
  show_query()
#> <SQL>
#> SELECT tailnum, "type", manufacturer, model, "year"
#> FROM planes

planes |> 
  select(tailnum, type, manufacturer, model, year) |> 
  rename(year_built = year) |> 
  show_query()
#> <SQL>
#> SELECT tailnum, "type", manufacturer, model, "year" AS year_built
#> FROM planes

planes |> 
  select(tailnum, type, manufacturer, model, year) |> 
  relocate(manufacturer, model, .before = type) |> 
  show_query()
#> <SQL>
#> SELECT tailnum, manufacturer, model, "type", "year"
#> FROM planes
```


This example also shows you how SQL does renaming. In SQL terminology renaming is calledaliasingand is done withAS. Note that unlikemutate(), the old name is on the left and the new name is on the right.


In the examples above note that"year"and"type"are wrapped in double quotes. That’s because these arereserved wordsin duckdb, so dbplyr quotes them to avoid any potential confusion between column/table names and SQL operators.


When working with other databases you’re likely to see every variable name quoted because only a handful of client packages, like duckdb, know what all the reserved words are, so they quote everything to be safe.


```
SELECT "tailnum", "type", "manufacturer", "model", "year"
FROM "planes"
```


Some other database systems use backticks instead of quotes:


```
SELECT `tailnum`, `type`, `manufacturer`, `model`, `year`
FROM `planes`
```


The translations formutate()are similarly straightforward: each variable becomes a new expression inSELECT:


```
flights |> 
  mutate(
    speed = distance / (air_time / 60)
  ) |> 
  show_query()
#> <SQL>
#> SELECT flights.*, distance / (air_time / 60.0) AS speed
#> FROM flights
```


We’ll come back to the translation of individual components (like/) inSection 21.6.


### 21.5.3FROM


TheFROMclause defines the data source. It’s going to be rather uninteresting for a little while, because we’re just using single tables. You’ll see more complex examples once we hit the join functions.


### 21.5.4GROUP BY


group_by()is translated to theGROUP BY6clause andsummarize()is translated to theSELECTclause:


```
diamonds_db |> 
  group_by(cut) |> 
  summarize(
    n = n(),
    avg_price = mean(price, na.rm = TRUE)
  ) |> 
  show_query()
#> <SQL>
#> SELECT cut, COUNT(*) AS n, AVG(price) AS avg_price
#> FROM diamonds
#> GROUP BY cut
```


We’ll come back to what’s happening with the translation ofn()andmean()inSection 21.6.


### 21.5.5WHERE


filter()is translated to theWHEREclause:


```
flights |> 
  filter(dest == "IAH" | dest == "HOU") |> 
  show_query()
#> <SQL>
#> SELECT flights.*
#> FROM flights
#> WHERE (dest = 'IAH' OR dest = 'HOU')

flights |> 
  filter(arr_delay > 0 & arr_delay < 20) |> 
  show_query()
#> <SQL>
#> SELECT flights.*
#> FROM flights
#> WHERE (arr_delay > 0.0 AND arr_delay < 20.0)
```


There are a few important details to note here:

- |becomesORand&becomesAND.
- SQL uses=for comparison, not==. SQL doesn’t have assignment, so there’s no potential for confusion there.
- SQL uses only''for strings, not"". In SQL,""is used to identify variables, like R’s``.

Another useful SQL operator isIN, which is very close to R’s%in%:


```
flights |> 
  filter(dest %in% c("IAH", "HOU")) |> 
  show_query()
#> <SQL>
#> SELECT flights.*
#> FROM flights
#> WHERE (dest IN ('IAH', 'HOU'))
```


SQL usesNULLinstead ofNA.NULLs behave similarly toNAs. The main difference is that while they’re “infectious” in comparisons and arithmetic, they are silently dropped when summarizing. dbplyr will remind you about this behavior the first time you hit it:


```
flights |> 
  group_by(dest) |> 
  summarize(delay = mean(arr_delay))
#> Warning: Missing values are always removed in SQL aggregation functions.
#> Use `na.rm = TRUE` to silence this warning
#> This warning is displayed once every 8 hours.
#> # Source:   SQL [?? x 2]
#> # Database: DuckDB 1.5.2 [unknown@Linux 6.17.0-1013-azure:R 4.6.0/:memory:]
#>   dest  delay
#>   <chr> <dbl>
#> 1 SFO    2.67
#> 2 GSP   15.9 
#> 3 SJU    2.52
#> 4 DCA    9.07
#> 5 SNA   -7.87
#> 6 GSO   14.1 
#> # ℹ more rows
```


If you want to learn more about howNULLs work, you might enjoy “The Three-Valued Logic of SQL” by Markus Winand.


In general, you can work withNULLs using the functions you’d use forNAs in R:


```
flights |> 
  filter(!is.na(dep_delay)) |> 
  show_query()
#> <SQL>
#> SELECT flights.*
#> FROM flights
#> WHERE (NOT((dep_delay IS NULL)))
```


This SQL query illustrates one of the drawbacks of dbplyr: while the SQL is correct, it isn’t as simple as you might write by hand. In this case, you could drop the parentheses and use a special operator that’s easier to read:


```
WHERE "dep_delay" IS NOT NULL
```


Note that if youfilter()a variable that you created using a summarize, dbplyr will generate aHAVINGclause, rather than aWHEREclause. This is a one of the idiosyncrasies of SQL:WHEREis evaluated beforeSELECTandGROUP BY, so SQL needs another clause that’s evaluated afterwards.


```
diamonds_db |> 
  group_by(cut) |> 
  summarize(n = n()) |> 
  filter(n > 100) |> 
  show_query()
#> <SQL>
#> SELECT cut, COUNT(*) AS n
#> FROM diamonds
#> GROUP BY cut
#> HAVING (COUNT(*) > 100.0)
```


### 21.5.6ORDER BY


Ordering rows involves a straightforward translation fromarrange()to theORDER BYclause:


```
flights |> 
  arrange(year, month, day, desc(dep_delay)) |> 
  show_query()
#> <SQL>
#> SELECT flights.*
#> FROM flights
#> ORDER BY "year", "month", "day", dep_delay DESC
```


Notice howdesc()is translated toDESC: this is one of the many dplyr functions whose name was directly inspired by SQL.


### 21.5.7Subqueries


Sometimes it’s not possible to translate a dplyr pipeline into a singleSELECTstatement and you need to use a subquery. Asubqueryis just a query used as a data source in theFROMclause, instead of the usual table.


dbplyr typically uses subqueries to work around limitations of SQL. For example, expressions in theSELECTclause can’t refer to columns that were just created. That means that the following (silly) dplyr pipeline needs to happen in two steps: the first (inner) query computesyear1and then the second (outer) query can computeyear2.


```
flights |> 
  mutate(
    year1 = year + 1,
    year2 = year1 + 1
  ) |> 
  show_query()
#> <SQL>
#> SELECT q01.*, year1 + 1.0 AS year2
#> FROM (
#>   SELECT flights.*, "year" + 1.0 AS year1
#>   FROM flights
#> ) q01
```


You’ll also see this if you attempted tofilter()a variable that you just created. Remember, even thoughWHEREis written afterSELECT, it’s evaluated before it, so we need a subquery in this (silly) example:


```
flights |> 
  mutate(year1 = year + 1) |> 
  filter(year1 == 2014) |> 
  show_query()
#> <SQL>
#> SELECT q01.*
#> FROM (
#>   SELECT flights.*, "year" + 1.0 AS year1
#>   FROM flights
#> ) q01
#> WHERE (year1 = 2014.0)
```


Sometimes dbplyr will create a subquery where it’s not needed because it doesn’t yet know how to optimize that translation. As dbplyr improves over time, these cases will get rarer but will probably never go away.


### 21.5.8Joins


If you’re familiar with dplyr’s joins, SQL joins are very similar. Here’s a simple example:


```
flights |> 
  left_join(planes |> rename(year_built = year), join_by(tailnum)) |> 
  show_query()
#> <SQL>
#> SELECT
#>   flights.*,
#>   planes."year" AS year_built,
#>   "type",
#>   manufacturer,
#>   model,
#>   engines,
#>   seats,
#>   speed,
#>   engine
#> FROM flights
#> LEFT JOIN planes
#>   ON (flights.tailnum = planes.tailnum)
```


The main thing to notice here is the syntax: SQL joins use sub-clauses of theFROMclause to bring in additional tables, usingONto define how the tables are related.


dplyr’s names for these functions are so closely connected to SQL that you can easily guess the equivalent SQL forinner_join(),right_join(), andfull_join():


```
SELECT flights.*, "type", manufacturer, model, engines, seats, speed
FROM flights
INNER JOIN planes ON (flights.tailnum = planes.tailnum)

SELECT flights.*, "type", manufacturer, model, engines, seats, speed
FROM flights
RIGHT JOIN planes ON (flights.tailnum = planes.tailnum)

SELECT flights.*, "type", manufacturer, model, engines, seats, speed
FROM flights
FULL JOIN planes ON (flights.tailnum = planes.tailnum)
```


You’re likely to need many joins when working with data from a database. That’s because database tables are often stored in a highly normalized form, where each “fact” is stored in a single place and to keep a complete dataset for analysis you need to navigate a complex network of tables connected by primary and foreign keys. If you hit this scenario, thedm package, by Tobias Schieferdecker, Kirill Müller, and Darko Bergant, is a life saver. It can automatically determine the connections between tables using the constraints that DBAs often supply, visualize the connections so you can see what’s going on, and generate the joins you need to connect one table to another.


### 21.5.9Other verbs


dbplyr also translates other verbs likedistinct(),slice_*(), andintersect(), and a growing selection of tidyr functions likepivot_longer()andpivot_wider(). The easiest way to see the full set of what’s currently available is to visit the dbplyr website:https://dbplyr.tidyverse.org/reference/.


### 21.5.10Exercises

- What isdistinct()translated to? How abouthead()?

What isdistinct()translated to? How abouthead()?

- Explain what each of the following SQL queries do and try recreate them using dbplyr.SELECT*FROMflightsWHEREdep_delay<arr_delaySELECT*, distance/(air_time/60)ASspeedFROMflights

Explain what each of the following SQL queries do and try recreate them using dbplyr.


```
SELECT * 
FROM flights
WHERE dep_delay < arr_delay

SELECT *, distance / (air_time / 60) AS speed
FROM flights
```


## 21.6Function translations


So far we’ve focused on the big picture of how dplyr verbs are translated to the clauses of a query. Now we’re going to zoom in a little and talk about the translation of the R functions that work with individual columns, e.g., what happens when you usemean(x)in asummarize()?


To help see what’s going on, we’ll use a couple of little helper functions that run asummarize()ormutate()and show the generated SQL. That will make it a little easier to explore a few variations and see how summaries and transformations can differ.


```
summarize_query <- function(df, ...) {
  df |> 
    summarize(...) |> 
    show_query()
}
mutate_query <- function(df, ...) {
  df |> 
    mutate(..., .keep = "none") |> 
    show_query()
}
```


Let’s dive in with some summaries! Looking at the code below you’ll notice that some summary functions, likemean(), have a relatively simple translation while others, likemedian(), are much more complex. The complexity is typically higher for operations that are common in statistics but less common in databases.


```
flights |> 
  group_by(year, month, day) |>  
  summarize_query(
    mean = mean(arr_delay, na.rm = TRUE),
    median = median(arr_delay, na.rm = TRUE)
  )
#> `summarise()` has grouped output by "year" and "month". You can override
#> using the `.groups` argument.
#> <SQL>
#> SELECT
#>   "year",
#>   "month",
#>   "day",
#>   AVG(arr_delay) AS mean,
#>   MEDIAN(arr_delay) AS median
#> FROM flights
#> GROUP BY "year", "month", "day"
```


The translation of summary functions becomes more complicated when you use them inside amutate()because they have to turn into so-calledwindowfunctions. In SQL, you turn an ordinary aggregation function into a window function by addingOVERafter it:


```
flights |> 
  group_by(year, month, day) |>  
  mutate_query(
    mean = mean(arr_delay, na.rm = TRUE),
  )
#> <SQL>
#> SELECT
#>   "year",
#>   "month",
#>   "day",
#>   AVG(arr_delay) OVER (PARTITION BY "year", "month", "day") AS mean
#> FROM flights
```


In SQL, theGROUP BYclause is used exclusively for summaries so here you can see that the grouping has moved from theGROUP BYclause toOVER.


Window functions include all functions that look forward or backwards, likelead()andlag()which look at the “previous” or “next” value respectively:


```
flights |> 
  group_by(dest) |>  
  arrange(time_hour) |> 
  mutate_query(
    lead = lead(arr_delay),
    lag = lag(arr_delay)
  )
#> <SQL>
#> SELECT
#>   dest,
#>   LEAD(arr_delay, 1, NULL) OVER (PARTITION BY dest ORDER BY time_hour) AS lead,
#>   LAG(arr_delay, 1, NULL) OVER (PARTITION BY dest ORDER BY time_hour) AS lag
#> FROM flights
#> ORDER BY time_hour
```


Here it’s important toarrange()the data, because SQL tables have no intrinsic order. In fact, if you don’t usearrange()you might get the rows back in a different order every time! Notice for window functions, the ordering information is repeated: theORDER BYclause of the main query doesn’t automatically apply to window functions.


Another important SQL function isCASE WHEN. It’s used as the translation ofif_else()andcase_when(), the dplyr function that it directly inspired. Here are a couple of simple examples:


```
flights |> 
  mutate_query(
    description = if_else(arr_delay > 0, "delayed", "on-time")
  )
#> <SQL>
#> SELECT CASE WHEN (arr_delay > 0.0) THEN 'delayed' WHEN NOT (arr_delay > 0.0) THEN 'on-time' END AS description
#> FROM flights
flights |> 
  mutate_query(
    description = 
      case_when(
        arr_delay < -5 ~ "early", 
        arr_delay < 5 ~ "on-time",
        arr_delay >= 5 ~ "late"
      )
  )
#> <SQL>
#> SELECT CASE
#> WHEN (arr_delay < -5.0) THEN 'early'
#> WHEN (arr_delay < 5.0) THEN 'on-time'
#> WHEN (arr_delay >= 5.0) THEN 'late'
#> END AS description
#> FROM flights
```


CASE WHENis also used for some other functions that don’t have a direct translation from R to SQL. A good example of this iscut():


```
flights |> 
  mutate_query(
    description =  cut(
      arr_delay, 
      breaks = c(-Inf, -5, 5, Inf), 
      labels = c("early", "on-time", "late")
    )
  )
#> <SQL>
#> SELECT CASE
#> WHEN (arr_delay <= -5.0) THEN 'early'
#> WHEN (arr_delay <= 5.0) THEN 'on-time'
#> WHEN (arr_delay > 5.0) THEN 'late'
#> END AS description
#> FROM flights
```


dbplyr also translates common string and date-time manipulation functions, which you can learn about invignette("translation-function", package = "dbplyr"). dbplyr’s translations are certainly not perfect, and there are many R functions that aren’t translated yet, but dbplyr does a surprisingly good job covering the functions that you’ll use most of the time.


## 21.7Summary


In this chapter you learned how to access data from databases. We focused on dbplyr, a dplyr “backend” that allows you to write the dplyr code you’re familiar with, and have it be automatically translated to SQL. We used that translation to teach you a little SQL; it’s important to learn some SQL because it’sthemost commonly used language for working with data and knowing some will make it easier for you to communicate with other data folks who don’t use R.


If you’ve finished this chapter and would like to learn more about SQL, we have two recommendations:

- SQL for Data Scientistsby Renée M. P. Teate is an introduction to SQL designed specifically for the needs of data scientists, and includes examples of the sort of highly interconnected data you’re likely to encounter in real organizations.
- Practical SQLby Anthony DeBarros is written from the perspective of a data journalist (a data scientist specialized in telling compelling stories) and goes into more detail about getting your data into a database and running your own DBMS.

In the next chapter, we’ll learn about another dplyr backend for working with large data: arrow. Arrow is designed for working with large files on disk, and is a natural complement to databases.

- SQL is either pronounced “s”-“q”-“l” or “sequel”.↩︎

SQL is either pronounced “s”-“q”-“l” or “sequel”.↩︎

- Typically, this is the only function you’ll use from the client package, so we recommend using::to pull out that one function, rather than loading the complete package withlibrary().↩︎

Typically, this is the only function you’ll use from the client package, so we recommend using::to pull out that one function, rather than loading the complete package withlibrary().↩︎

- At least, all the tables that you have permission to see.↩︎

At least, all the tables that you have permission to see.↩︎

- Confusingly, depending on the context,SELECTis either a statement or a clause. To avoid this confusion, we’ll generally useSELECTquery instead ofSELECTstatement.↩︎

Confusingly, depending on the context,SELECTis either a statement or a clause. To avoid this confusion, we’ll generally useSELECTquery instead ofSELECTstatement.↩︎

- Ok, technically, only theSELECTis required, since you can write queries likeSELECT 1+1to perform basic calculations. But if you want to work with data (as you always do!) you’ll also need aFROMclause.↩︎

Ok, technically, only theSELECTis required, since you can write queries likeSELECT 1+1to perform basic calculations. But if you want to work with data (as you always do!) you’ll also need aFROMclause.↩︎

- This is no coincidence: the dplyr function name was inspired by the SQL clause.↩︎

This is no coincidence: the dplyr function name was inspired by the SQL clause.↩︎
