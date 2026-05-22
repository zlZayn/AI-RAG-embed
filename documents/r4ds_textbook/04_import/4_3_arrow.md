- Import
- 22Arrow

# 22Arrow


## 22.1Introduction


CSV files are designed to be easily read by humans. They’re a good interchange format because they’re very simple and they can be read by every tool under the sun. But CSV files aren’t very efficient: you have to do quite a lot of work to read the data into R. In this chapter, you’ll learn about a powerful alternative: theparquet format, an open standards-based format widely used by big data systems.


We’ll pair parquet files withApache Arrow, a multi-language toolbox designed for efficient analysis and transport of large datasets. We’ll use Apache Arrow via thearrow package, which provides a dplyr backend allowing you to analyze larger-than-memory datasets using familiar dplyr syntax. As an additional benefit, arrow is extremely fast: you’ll see some examples later in the chapter.


Both arrow and dbplyr provide dplyr backends, so you might wonder when to use each. In many cases, the choice is made for you, as the data is already in a database or in parquet files, and you’ll want to work with it as is. But if you’re starting with your own data (perhaps CSV files), you can either load it into a database or convert it to parquet. In general, it’s hard to know what will work best, so in the early stages of your analysis we’d encourage you to try both and pick the one that works the best for you.


(A big thanks to Danielle Navarro who contributed the initial version of this chapter.)


### 22.1.1Prerequisites


In this chapter, we’ll continue to use the tidyverse, particularly dplyr, but we’ll pair it with the arrow package which is designed specifically for working with large data.


```
library(tidyverse)
library(arrow)
```


Later in the chapter, we’ll also see some connections between arrow and duckdb, so we’ll also need dbplyr and duckdb.


```
library(dbplyr, warn.conflicts = FALSE)
library(duckdb)
#> Loading required package: DBI
```


## 22.2Getting the data


We begin by getting a dataset worthy of these tools: a dataset of item checkouts from Seattle public libraries, available online atdata.seattle.gov/Community/Checkouts-by-Title/tmmm-ytt6. This dataset contains 41,389,465 rows that tell you how many times each book was checked out each month from April 2005 to October 2022.


The following code will get you a cached copy of the data. The data is a 9GB CSV file, so it will take some time to download. I highly recommend usingcurl::multi_download()to get very large files as it’s built for exactly this purpose: it gives you a progress bar and it can resume the download if its interrupted.


```
dir.create("data", showWarnings = FALSE)

curl::multi_download(
  "https://r4ds.s3.us-west-2.amazonaws.com/seattle-library-checkouts.csv",
  "data/seattle-library-checkouts.csv",
  resume = TRUE
)
#> # A tibble: 1 × 10
#>   success status_code resumefrom url                    destfile        error
#>   <lgl>         <int>      <dbl> <chr>                  <chr>           <chr>
#> 1 TRUE            200          0 https://r4ds.s3.us-we… data/seattle-l… <NA> 
#> # ℹ 4 more variables: type <chr>, modified <dttm>, time <dbl>,
#> #   headers <list>
```


## 22.3Opening a dataset


Let’s start by taking a look at the data. At 9 GB, this file is large enough that we probably don’t want to load the whole thing into memory. A good rule of thumb is that you usually want at least twice as much memory as the size of the data, and many laptops top out at 16 GB. This means we want to avoidread_csv()and instead use thearrow::open_dataset():


```
seattle_csv <- open_dataset(
  sources = "data/seattle-library-checkouts.csv", 
  col_types = schema(ISBN = string()),
  format = "csv"
)
```


What happens when this code is run?open_dataset()will scan a few thousand rows to figure out the structure of the dataset. TheISBNcolumn contains blank values for the first 80,000 rows, so we have to specify the column type to help arrow work out the data structure. Once the data has been scanned byopen_dataset(), it records what it’s found and stops; it will only read further rows as you specifically request them. This metadata is what we see if we printseattle_csv:


```
seattle_csv
#> FileSystemDataset with 1 csv file
#> UsageClass: string
#> CheckoutType: string
#> MaterialType: string
#> CheckoutYear: int64
#> CheckoutMonth: int64
#> Checkouts: int64
#> Title: string
#> ISBN: string
#> Creator: string
#> Subjects: string
#> Publisher: string
#> PublicationYear: string
```


The first line in the output tells you thatseattle_csvis stored locally on-disk as a single CSV file; it will only be loaded into memory as needed. The remainder of the output tells you the column type that arrow has imputed for each column.


We can see what’s actually in withglimpse(). This reveals that there are ~41 million rows and 12 columns, and shows us a few values.


```
seattle_csv |> glimpse()
#> FileSystemDataset with 1 csv file
#> 41,389,465 rows x 12 columns
#> $ UsageClass      <string> "Physical", "Physical", "Digital", "Physical", "Ph…
#> $ CheckoutType    <string> "Horizon", "Horizon", "OverDrive", "Horizon", "Hor…
#> $ MaterialType    <string> "BOOK", "BOOK", "EBOOK", "BOOK", "SOUNDDISC", "BOO…
#> $ CheckoutYear     <int64> 2016, 2016, 2016, 2016, 2016, 2016, 2016, 2016, 20…
#> $ CheckoutMonth    <int64> 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,…
#> $ Checkouts        <int64> 1, 1, 1, 1, 1, 1, 1, 1, 4, 1, 1, 2, 3, 2, 1, 3, 2,…
#> $ Title           <string> "Super rich : a guide to having it all / Russell S…
#> $ ISBN            <string> "", "", "", "", "", "", "", "", "", "", "", "", ""…
#> $ Creator         <string> "Simmons, Russell", "Barclay, James, 1965-", "Tim …
#> $ Subjects        <string> "Self realization, Conduct of life, Attitude Psych…
#> $ Publisher       <string> "Gotham Books,", "Pyr,", "Random House, Inc.", "Di…
#> $ PublicationYear <string> "c2011.", "2010.", "2015", "2005.", "c2004.", "c20…
```


We can start to use this dataset with dplyr verbs, usingcollect()to force arrow to perform the computation and return some data. For example, this code tells us the total number of checkouts per year:


```
seattle_csv |> 
  group_by(CheckoutYear) |> 
  summarise(Checkouts = sum(Checkouts)) |> 
  arrange(CheckoutYear) |> 
  collect()
#> # A tibble: 18 × 2
#>   CheckoutYear Checkouts
#>          <int>     <int>
#> 1         2005   3798685
#> 2         2006   6599318
#> 3         2007   7126627
#> 4         2008   8438486
#> 5         2009   9135167
#> 6         2010   8608966
#> # ℹ 12 more rows
```


Thanks to arrow, this code will work regardless of how large the underlying dataset is. But it’s currently rather slow: on Hadley’s computer, it took ~10s to run. That’s not terrible given how much data we have, but we can make it much faster by switching to a better format.


## 22.4The parquet format


To make this data easier to work with, let’s switch to the parquet file format and split it up into multiple files. The following sections will first introduce you to parquet and partitioning, and then apply what we learned to the Seattle library data.


### 22.4.1Advantages of parquet


Like CSV, parquet is used for rectangular data, but instead of being a text format that you can read with any file editor, it’s a custom binary format designed specifically for the needs of big data. This means that:

- Parquet files are usually smaller than the equivalent CSV file. Parquet relies onefficient encodingsto keep file size down, and supports file compression. This helps make parquet files fast because there’s less data to move from disk to memory.

Parquet files are usually smaller than the equivalent CSV file. Parquet relies onefficient encodingsto keep file size down, and supports file compression. This helps make parquet files fast because there’s less data to move from disk to memory.

- Parquet files have a rich type system. As we talked about inSection 7.3, a CSV file does not provide any information about column types. For example, a CSV reader has to guess whether"08-10-2022"should be parsed as a string or a date. In contrast, parquet files store data in a way that records the type along with the data.

Parquet files have a rich type system. As we talked about inSection 7.3, a CSV file does not provide any information about column types. For example, a CSV reader has to guess whether"08-10-2022"should be parsed as a string or a date. In contrast, parquet files store data in a way that records the type along with the data.

- Parquet files are “column-oriented”. This means that they’re organized column-by-column, much like R’s data frame. This typically leads to better performance for data analysis tasks compared to CSV files, which are organized row-by-row.

Parquet files are “column-oriented”. This means that they’re organized column-by-column, much like R’s data frame. This typically leads to better performance for data analysis tasks compared to CSV files, which are organized row-by-row.

- Parquet files are “chunked”, which makes it possible to work on different parts of the file at the same time, and, if you’re lucky, to skip some chunks altogether.

Parquet files are “chunked”, which makes it possible to work on different parts of the file at the same time, and, if you’re lucky, to skip some chunks altogether.


There’s one primary disadvantage to parquet files: they are no longer “human readable”, i.e. if you look at a parquet file usingreadr::read_file(), you’ll just see a bunch of gibberish.


### 22.4.2Partitioning


As datasets get larger and larger, storing all the data in a single file gets increasingly painful and it’s often useful to split large datasets across many files. When this structuring is done intelligently, this strategy can lead to significant improvements in performance because many analyses will only require a subset of the files.


There are no hard and fast rules about how to partition your dataset: the results will depend on your data, access patterns, and the systems that read the data. You’re likely to need to do some experimentation before you find the ideal partitioning for your situation. As a rough guide, arrow suggests that you avoid files smaller than 20MB and larger than 2GB and avoid partitions that produce more than 10,000 files. You should also try to partition by variables that you filter by; as you’ll see shortly, that allows arrow to skip a lot of work by reading only the relevant files.


### 22.4.3Rewriting the Seattle library data


Let’s apply these ideas to the Seattle library data to see how they play out in practice. We’re going to partition byCheckoutYear, since it’s likely some analyses will only want to look at recent data and partitioning by year yields 18 chunks of a reasonable size.


To rewrite the data we define the partition usingdplyr::group_by()and then save the partitions to a directory witharrow::write_dataset().write_dataset()has two important arguments: a directory where we’ll create the files and the format we’ll use.


```
pq_path <- "data/seattle-library-checkouts"
```


```
seattle_csv |>
  group_by(CheckoutYear) |>
  write_dataset(path = pq_path, format = "parquet")
```


This takes about a minute to run; as we’ll see shortly this is an initial investment that pays off by making future operations much much faster.


Let’s take a look at what we just produced:


```
tibble(
  files = list.files(pq_path, recursive = TRUE),
  size_MB = file.size(file.path(pq_path, files)) / 1024^2
)
#> # A tibble: 18 × 2
#>   files                            size_MB
#>   <chr>                              <dbl>
#> 1 CheckoutYear=2005/part-0.parquet    109.
#> 2 CheckoutYear=2006/part-0.parquet    164.
#> 3 CheckoutYear=2007/part-0.parquet    178.
#> 4 CheckoutYear=2008/part-0.parquet    195.
#> 5 CheckoutYear=2009/part-0.parquet    214.
#> 6 CheckoutYear=2010/part-0.parquet    222.
#> # ℹ 12 more rows
```


Our single 9GB CSV file has been rewritten into 18 parquet files. The file names use a “self-describing” convention used by theApache Hiveproject. Hive-style partitions name folders with a “key=value” convention, so as you might guess, theCheckoutYear=2005directory contains all the data whereCheckoutYearis 2005. Each file is between 100 and 300 MB and the total size is now around 4 GB, a little over half the size of the original CSV file. This is as we expect since parquet is a much more efficient format.


## 22.5Using dplyr with arrow


Now we’ve created these parquet files, we’ll need to read them in again. We useopen_dataset()again, but this time we give it a directory:


```
seattle_pq <- open_dataset(pq_path)
```


Now we can write our dplyr pipeline. For example, we could count the total number of books checked out in each month for the last five years:


```
query <- seattle_pq |> 
  filter(CheckoutYear >= 2018, MaterialType == "BOOK") |>
  group_by(CheckoutYear, CheckoutMonth) |>
  summarize(TotalCheckouts = sum(Checkouts)) |>
  arrange(CheckoutYear, CheckoutMonth)
```


Writing dplyr code for arrow data is conceptually similar to dbplyr,Chapter 21: you write dplyr code, which is automatically transformed into a query that the Apache Arrow C++ library understands, which is then executed when you callcollect(). If we print out thequeryobject we can see a little information about what we expect Arrow to return when the execution takes place:


```
query
#> FileSystemDataset (query)
#> CheckoutYear: int32
#> CheckoutMonth: int64
#> TotalCheckouts: int64
#> 
#> * Grouped by CheckoutYear
#> * Sorted by CheckoutYear [asc], CheckoutMonth [asc]
#> See $.data for the source Arrow object
```


And we can get the results by callingcollect():


```
query |> collect()
#> # A tibble: 58 × 3
#> # Groups:   CheckoutYear [5]
#>   CheckoutYear CheckoutMonth TotalCheckouts
#>          <int>         <int>          <int>
#> 1         2018             1         355101
#> 2         2018             2         309813
#> 3         2018             3         344487
#> 4         2018             4         330988
#> 5         2018             5         318049
#> 6         2018             6         341825
#> # ℹ 52 more rows
```


Like dbplyr, arrow only understands some R expressions, so you may not be able to write exactly the same code you usually would. However, the list of operations and functions supported is fairly extensive and continues to grow; find a complete list of currently supported functions in?acero.


### 22.5.1Performance


Let’s take a quick look at the performance impact of switching from CSV to parquet. First, let’s time how long it takes to calculate the number of books checked out in each month of 2021, when the data is stored as a single large csv:


```
seattle_csv |> 
  filter(CheckoutYear == 2021, MaterialType == "BOOK") |>
  group_by(CheckoutMonth) |>
  summarize(TotalCheckouts = sum(Checkouts)) |>
  arrange(desc(CheckoutMonth)) |>
  collect() |> 
  system.time()
#>    user  system elapsed 
#>  11.951   1.297  11.387
```


Now let’s use our new version of the dataset in which the Seattle library checkout data has been partitioned into 18 smaller parquet files:


```
seattle_pq |> 
  filter(CheckoutYear == 2021, MaterialType == "BOOK") |>
  group_by(CheckoutMonth) |>
  summarize(TotalCheckouts = sum(Checkouts)) |>
  arrange(desc(CheckoutMonth)) |>
  collect() |> 
  system.time()
#>    user  system elapsed 
#>   0.263   0.058   0.063
```


The ~100x speedup in performance is attributable to two factors: the multi-file partitioning, and the format of individual files:

- Partitioning improves performance because this query usesCheckoutYear == 2021to filter the data, and arrow is smart enough to recognize that it only needs to read 1 of the 18 parquet files.
- The parquet format improves performance by storing data in a binary format that can be read more directly into memory. The column-wise format and rich metadata means that arrow only needs to read the four columns actually used in the query (CheckoutYear,MaterialType,CheckoutMonth, andCheckouts).

This massive difference in performance is why it pays off to convert large CSVs to parquet!


### 22.5.2Using duckdb with arrow


There’s one last advantage of parquet and arrow — it’s very easy to turn an arrow dataset into a DuckDB database (Chapter 21) by callingarrow::to_duckdb():


```
seattle_pq |> 
  to_duckdb() |>
  filter(CheckoutYear >= 2018, MaterialType == "BOOK") |>
  group_by(CheckoutYear) |>
  summarize(TotalCheckouts = sum(Checkouts)) |>
  arrange(desc(CheckoutYear)) |>
  collect()
#> Warning: Missing values are always removed in SQL aggregation functions.
#> Use `na.rm = TRUE` to silence this warning
#> This warning is displayed once every 8 hours.
#> # A tibble: 5 × 2
#>   CheckoutYear TotalCheckouts
#>          <int>          <dbl>
#> 1         2022        2431502
#> 2         2021        2266438
#> 3         2020        1241999
#> 4         2019        3931688
#> 5         2018        3987569
```


The neat thing aboutto_duckdb()is that the transfer doesn’t involve any memory copying, and speaks to the goals of the arrow ecosystem: enabling seamless transitions from one computing environment to another.


### 22.5.3Exercises

- Figure out the most popular book each year.
- Which author has the most books in the Seattle library system?
- How has checkouts of books vs ebooks changed over the last 10 years?

## 22.6Summary


In this chapter, you’ve been given a taste of the arrow package, which provides a dplyr backend for working with large on-disk datasets. It can work with CSV files, and it’s much much faster if you convert your data to parquet. Parquet is a binary data format that’s designed specifically for data analysis on modern computers. Far fewer tools can work with parquet files compared to CSV, but its partitioned, compressed, and columnar structure makes it much more efficient to analyze.


Next up you’ll learn about your first non-rectangular data source, which you’ll handle using tools provided by the tidyr package. We’ll focus on data that comes from JSON files, but the general principles apply to tree-like data regardless of its source.
