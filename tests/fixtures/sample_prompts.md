# Sample Prompts for Testing

These prompts demonstrate common use cases for batch LLM processing.

## Product Enrichment

Analyze this product and extract key information:

**Name:** {name}
**Description:** {description}
**Category:** {category}

Return a JSON object with:
- `sentiment`: "positive", "neutral", or "negative" based on the description
- `keywords`: array of 3-5 relevant keywords
- `suggested_price_range`: "budget", "mid-range", or "premium"
- `target_audience`: brief description of ideal customer

## Translation

Translate the following text from {source_lang} to Spanish:

{text}

Return a JSON object with:
- `translation`: the translated text
- `confidence`: a number from 0.0 to 1.0 indicating translation confidence

## Sentiment Analysis

Analyze the sentiment of this product review:

**Product:** {product}
**Review:** {review}
**Rating:** {rating}/5

Return a JSON object with:
- `sentiment`: "positive", "negative", or "mixed"
- `summary`: one-sentence summary of the review
- `key_points`: array of main points mentioned
- `improvement_suggestions`: array of suggestions for the product (if any)

## Categorization

Categorize this item:

**Name:** {name}
**Description:** {description}

Return a JSON object with:
- `category`: primary category
- `subcategory`: more specific subcategory
- `tags`: array of relevant tags

## Data Extraction

Extract structured data from this text:

{content}

Return a JSON object containing all identifiable entities such as:
- `names`: array of person names
- `locations`: array of places
- `dates`: array of dates mentioned
- `organizations`: array of company/org names
- `numbers`: array of numerical values with context
