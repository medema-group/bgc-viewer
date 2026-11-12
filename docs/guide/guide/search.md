# Searching

When the viewer reads an indexed dataset from the backend (see
[Data Sources & Formats](./data-sources.md#bgc-viewer-api-backend-with-database)),
the **Search** button in the header, or <kbd>Ctrl</kbd>+<kbd>K</kbd>, opens a
search across every region in the dataset. Clicking a result opens its record
at that region.

The search works on antiSMASH regions. Each region holds the products and
categories of its protoclusters and the results of the antiSMASH analysis
modules for it: functional domains, NRPS/PKS predictions, terpene and RiPP
results, comparisons with known clusters, and regulation. The field list under
**Search help** describes every field and where its values come from.

## Query builder

The query builder asks a question one row at a time. Each row compares one
field to a value: pick the field group, the field, the operator, and the
value.

| Operator | Matches regions where |
| --- | --- |
| is, is not | some value is (or no value is) exactly the given one |
| is any of, is none of | some value is (or no value is) in the list |
| contains, does not contain, starts with, ends with | some value contains the text, ignoring case |
| greater than, at least, less than, at most, between | some number compares so; leave one side of *between* empty for an open range |
| has a value, has no value | the field has some value, or none at all |

*is* and *is any of* match whole values, including case, so pick their values
from the suggestions. The suggestions show how many regions hold each value
and narrow as you type; press <kbd>Enter</kbd> to use the typed text as it is.

Rows after the first start with **AND** or **OR**, and AND binds before OR, as
in most query languages: *a AND b OR c* means *(a AND b) OR c*. Use
**+ Add group** for other brackets. The summary under the rows spells out the
question as the search will run it.

Two conditions reach beyond a single field:

- **Any text contains** (under *General*) finds each word inside any text value
  of a region, ignoring case.
- **Query string** (under *General*) puts a query in the query language below
  among the rows.

Pressing **Search** without conditions (**Browse all**) lists every region.

## Results

**Show Regions** lists one row per matching region. **Show Records** lists
each record with at least one matching region once. The counter below the
table counts matching regions in both cases.

Click a column heading to sort by it, again to reverse the order, and a third
time to go back to the default order. Only columns with one value per region
can be sorted.

The **Refine** panel beside the results lists the most common product
categories, products, organisms, and known-cluster compounds among all
matching regions. Click one to add it as a condition and search again.

## Query string

The **Query string** tab takes a query in the Tantivy query language, such as
`pfam:PF00550 AND substrates:Leu` or `product_category:RiPP NOT organism:"Streptomyces coelicolor A3(2)"`.
A bare word searches every text field; `field:value` searches one field, using
the field names listed under **Search help**, which also has examples built from
your dataset. For how fields match, see the [search index guide](../development/search-index.md#query-language).
