# ### Configure OpenAI API Key.

# In[1]:


# Install the OpenAI Python package.
get_ipython().run_line_magic('pip', 'install openai')


# In[2]:


import openai
from openai import OpenAI

client = OpenAI(
    api_key="write API KEY here"

completion = client.chat.completions.create(
  model="gpt-4o",  # Try a standard model,
  messages=[
    {"role": "user", "content": "Hello!"}
  ]
)

# Print the response
print(completion['choices'][0]['message']['content'])


# In[3]:


# Code example of reading input data

import pandas as pd
from IPython.display import display

def read_data_frame(document_id, sheet_name):
    export_link = f"https://docs.google.com/spreadsheets/d/{document_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    return  pd.read_csv(export_link)

document_id = '14fKHsblfqZfWj3iAaM2oA51TlYfQlFT4WKo52fVaQ9U'
products_df = read_data_frame(document_id, 'products')
emails_df = read_data_frame(document_id, 'emails')

# Display first 3 rows of each DataFrame
display(products_df.head(3))
display(emails_df.head(3))


# # Task 1. Classify emails

# In[4]:


# Function to classify emails using GPT-4o
def classify_email(email_subject, email_body):
    prompt = f"Classify the following email:\nSubject: {email_subject}\nBody: {email_body}\n\nCategory (product inquiry or order request OR if you are not able to identify then give unknown):"

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=10,
        n=1,
        stop=None,
        temperature=0.5
    )

    return response.choices[0].message.content.strip()

# Create a new DataFrame to store email classifications
email_classifications = []

for index, row in emails_df.iterrows():
    email_id = row['email_id']
    subject = row['subject']
    body = row['message']

    category = classify_email(subject, body)
    email_classifications.append({'email ID': email_id, 'category': category})

email_classifications_df = pd.DataFrame(email_classifications)

# Display the classification results
display(email_classifications_df.head())


# In[5]:


# Create a new DataFrame to store product info classifications
product_info_classifications = []

for index, row in products_df.iterrows():
    product_id = row['product_id']
    name = row['name']
    stock = row['stock']


    product_info_classifications.append({'product ID': product_id, 'name': name, 'stock':stock})

product_info_classifications_df = pd.DataFrame(product_info_classifications)
display(product_info_classifications_df.head())


# In[5]:
# # Task 2. Process order requests

# In[6]:
order_placement_log = []

def extract_product_id_and_quantity(order_request, product_info_classifications_df):
    prompt = f"""Extract the product IDs and quantities from the following message:\n\n{order_request}\n\n
                Respond with 'Product ID: [ID], Quantity: [Quantity]' for each product found. The Product ID may contain spaces or special characters.\n
                If a product is not found, use the {product_info_classifications_df} data to identify it.\n
                If someone requests "all," respond with 'all' as the quantity.\n
                If two values are present, take the minimum value."""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,  # Increased max_tokens to accommodate multiple products
        n=1,
        stop=None,
        temperature=0.5
    )

    response_text = response.choices[0].message.content.strip()
    print(response_text)

    # Improved parsing logic to handle IDs with spaces or special characters
    extracted_products = []
    lines = response_text.splitlines()
    for line in lines:
        if "Product ID:" in line and "Quantity:" in line:
            try:
                # Removing spaces within the product ID to handle spaced IDs "
                product_id = line.split("Product ID: ")[1].split(", Quantity:")[0].strip().replace(" ", "")
                quantity_string = line.split("Quantity: ")[1].strip()
                try:
                    quantity = int(quantity_string)
                except ValueError:
                    if quantity_string.lower() == 'all':
                        quantity = "all"
                    else:
                        quantity = 0
                extracted_products.append({'product_id': product_id, 'quantity': quantity})
            except IndexError:
                continue  # Skip lines that don't match the expected format

    return extracted_products

def process_order_request(email_id, order_request, product_info_classifications_df):
    products_to_order = extract_product_id_and_quantity(order_request, product_info_classifications_df)

    # Check stock availability for all products in the order
    all_in_stock = True
    for product in products_to_order:
        product_id = product['product_id']
        quantity = product['quantity']

        # Find the product in the products_df
        product_row = products_df[products_df['product_id'] == product_id]

        if not product_row.empty:
            available_stock = product_row['stock'].values[0]
            if quantity == 'all':
                quantity = available_stock
            if available_stock < quantity:
                all_in_stock = False
                break
        else:
            all_in_stock = False
            break

    # Process the order only if all items are in stock
    if all_in_stock:
        for product in products_to_order:
            product_id = product['product_id']
            quantity = product['quantity']

            product_row = products_df[products_df['product_id'] == product_id]
            available_stock = product_row['stock'].values[0]

            if quantity == 'all':
                quantity = available_stock

            # Update stock
            products_df.loc[products_df['product_id'] == product_id, 'stock'] -= quantity

            # Log the placed order
            order_placement_log.append({
                'product_id': product_id,
                'ordered_quantity': quantity,
                'available_stock': available_stock - quantity
            })

            order_status.append({
                'email_id': email_id,
                'product_id': product_id,
                'quantity': quantity,
                'status': "created"
            })
    else:
        for product in products_to_order:
            product_id = product['product_id']
            quantity = product['quantity']

            order_status.append({
                'email_id': email_id,
                'product_id': product_id,
                'quantity': quantity,
                'status': "order not created due to insufficient stock"
            })

# Process orders
order_status = []
for index, row in email_classifications_df.iterrows():
    if row['category'].lower() == 'category: order request':
        email_id = row['email ID']
        order_request = emails_df[emails_df['email_id'] == email_id]['message'].values[0]
        process_order_request(email_id, order_request, product_info_classifications_df)

# Convert the order status list to a DataFrame
order_status_df = pd.DataFrame(order_status)


# Display the order status and responses
print("Order Status:")
print(order_status_df.head())

print("Order Placement Log:")
print(order_placement_log)


# In[7]:
# Initialize an empty dictionary to store responses by email ID
order_responses = {}

# Iterate through the order status DataFrame
for index, row in order_status_df.iterrows():
    email_id = row['email_id']
    product = products_df[products_df['product_id'] == row['product_id']]

    if product.empty:
        product_name = "Unknown Product"
        quantity = row['quantity']
        response = f"We couldn't find the product you requested. Please check your order details."
    else:
        product_name = product['name'].values[0]
        quantity = row['quantity']

        # Create a response based on the order status
        if row['status'] == 'created':
            response = f"Dear Customer,\n\nYour order for {quantity} unit(s) of {product_name} has been successfully processed. Thank you for shopping with us!\n\nBest regards,\nYour Company"
        else:
            response = f"Dear Customer,\n\nUnfortunately, we could not fulfill your order for {quantity} unit(s) of {product_name} due to insufficient stock. We apologize for the inconvenience.\n\nPlease let us know if you would like to wait for a restock or if you would prefer to choose an alternative product.\n\nBest regards,\nYour Company"

    # Consolidate responses by email ID
    if email_id in order_responses:
        order_responses[email_id] += f"\n\n{response}"
    else:
        order_responses[email_id] = response

# Convert the consolidated responses to a DataFrame
order_responses_df = pd.DataFrame(order_responses.items(), columns=['email_id', 'response'])

# Display the consolidated order responses
print(order_responses_df.head())


# ## below code also work using gpt-4 but due to token limit, not able to use it.

# In[8]:


"""# Initialize an empty dictionary to store responses by email ID
order_responses = {}

# Iterate through the order status DataFrame
for index, row in order_status_df.iterrows():
    email_id = row['email_id']
    product = products_df[products_df['product_id'] == row['product_id']]

    if product.empty:
        product_name = "Unknown Product"
        quantity = row['quantity']
        response = f"We couldn't find the product you requested. Please check your order details."
    else:
        product_name = product['name'].values[0]
        quantity = row['quantity']

        # Prepare context for the API prompt
        if row['status'] == 'created':
            prompt = f"Please write a polite response informing the customer that their order for {quantity} unit(s) of {product_name} has been successfully processed."
        else:
            prompt = f"Please write a polite response informing the customer that their order for {quantity} unit(s) of {product_name} could not be fulfilled due to insufficient stock. Apologize for the inconvenience."

        # Call OpenAI API to generate the response
        api_response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            n=1,
            stop=None,
            temperature=0.5
        )

        response = api_response.choices[0].message.content.strip()

    # Consolidate responses by email ID
    if email_id in order_responses:
        order_responses[email_id] += f" {response}"
    else:
        order_responses[email_id] = response

# Convert the consolidated responses to a DataFrame
order_responses_df = pd.DataFrame(order_responses.items(), columns=['email_id', 'response'])

# Display the consolidated order responses
print(order_responses_df.head())"""


# In[8]:

# # Task 3. Handle product inquiry

# In[9]:
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
# In[10]:
"""product_catalog = products_df[['product_id', 'name', 'description']].copy()  # Explicitly create a copy
product_catalog['text'] = product_catalog['name'] + " " + product_catalog['description']
# Function to generate a response using OpenAI's API
def generate_response_with_openai(email_body, product_catalog):
    # Create a prompt that includes the email body and the product catalog information
    prompt = f"You are a helpful assistant. Based on the following email, provide a detailed response about the products mentioned:\n\nEmail: {email_body}\n\nAvailable Products:\n"

    for _, row in product_catalog.iterrows():
        prompt += f"Product: {row['name']}\nDescription: {row['description']}\n\n"

    # Query OpenAI's API
    response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            n=1,
            stop=None,
            temperature=0.5
    )

    # Extract and return the response
    return response.choices[0].message.content.strip()

# Process product inquiries using OpenAI
inquiry_responses = []

for index, row in emails_df.iterrows():
    email_id = row['email_id']
    subject = row['subject']
    body = row['message']

    # Classify the email
    category = classify_email(subject, body)

    if 'product inquiry' in category:
        # Generate a response using OpenAI
        response = generate_response_with_openai(body, product_catalog)
        inquiry_responses.append({'email ID': email_id, 'response': response})

# Convert the inquiry responses list to a DataFrame
inquiry_responses_df = pd.DataFrame(inquiry_responses)

print(inquiry_responses_df.head())"""


# In[11]:


# Assuming products_df has a 'stock' column that indicates the stock level of each product

product_catalog = products_df[['product_id', 'name', 'description', 'stock']].copy()  # Explicitly create a copy
product_catalog['text'] = product_catalog['name'] + " " + product_catalog['description']

vectorizer = TfidfVectorizer()
product_tfidf = vectorizer.fit_transform(product_catalog['text'])

def extract_product_info(email_body, product_catalog, product_tfidf):
    # Vectorize the email body
    email_tfidf = vectorizer.transform([email_body])

    # Calculate cosine similarity between the email and the product catalog
    similarities = cosine_similarity(email_tfidf, product_tfidf).flatten()

    # Find the most similar product
    most_similar_idx = similarities.argmax()
    if similarities[most_similar_idx] > 0.1:  # A threshold to ensure relevance
        product_info = product_catalog.iloc[most_similar_idx]

        # Check stock availability
        if product_info['stock'] > 0:
            response = f"Our {product_info['name']} is available. {product_info['description']}"
        else:
            response = f"Unfortunately, our {product_info['name']} is currently out of stock. Please check back later or explore other options."
    else:
        response = "Could you please provide more details about the product you're interested in?"

    return response

# Process product inquiries
inquiry_responses = []

for index, row in emails_df.iterrows():
    email_id = row['email_id']
    subject = row['subject']
    body = row['message']

    # Classify the email
    category = classify_email(subject, body)

    if 'product inquiry' in category.lower():
        # Extract product information and generate a response
        response = extract_product_info(body, product_catalog, product_tfidf)
        inquiry_responses.append({'email ID': email_id, 'response': response})

# Convert the inquiry responses list to a DataFrame
inquiry_responses_df = pd.DataFrame(inquiry_responses)

print(inquiry_responses_df.head())

# In[12]:
with pd.ExcelWriter('expected_output.xlsx') as writer:
    products_df.to_excel(writer, sheet_name='Products', index=False)
    emails_df.to_excel(writer, sheet_name='Emails', index=False)
    email_classifications_df.to_excel(writer, sheet_name='Email Classifications', index=False)
    order_status_df.to_excel(writer, sheet_name='Order Status', index=False)
    order_responses_df.to_excel(writer, sheet_name='Order Responses', index=False)
    inquiry_responses_df.to_excel(writer, sheet_name='Inquiry Responses', index=False)



