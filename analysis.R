# Analyse the pipeline output from R.
# install.packages(c("DBI", "RSQLite", "ggplot2"))
library(DBI)
library(RSQLite)
library(ggplot2)

con <- dbConnect(SQLite(), "data/kenya.db")
growth <- dbGetQuery(con, "SELECT * FROM kenya_growth ORDER BY year")
dbDisconnect(con)

ggplot(growth, aes(year, gdp_per_capita_usd)) +
  geom_line(linewidth = 1) +
  labs(title = "Kenya: GDP per capita (current US$)",
       x = NULL, y = NULL,
       caption = "Source: World Bank, loaded via etl.py") +
  theme_minimal()

ggsave("r/gdp_per_capita.png", width = 8, height = 4.5, dpi = 150)
