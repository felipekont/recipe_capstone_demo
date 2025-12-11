"""
Recipe Nutrition Filtering App
Streamlit interface for querying recipes by calorie range, macro percentages, and dietary preferences
Database: PostgreSQL (recipes_db)
Author: Felipe Contreras
"""

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

# PAGE CONFIGURATION

st.set_page_config(
    page_title="Recipe Macro Filter",
    layout="wide"
)

# DATABASE CONNECTION
@st.cache_resource
def get_database_connection():
    """Create and cache database connection using Streamlit Secrets"""
    try:
        # This looks for the secret named "db_url" on the cloud
        db_url = st.secrets["db_url"]
        
        # Create the engine
        engine = create_engine(db_url)
        
        # Test the connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
        
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        st.stop()


# HELPER FUNCTIONS

@st.cache_data(ttl=3600)
def get_categories():
    """Fetch all categories for dropdown filter"""
    query = "SELECT category_name FROM categories ORDER BY category_name"
    df = pd.read_sql(query, engine)
    return ['All Categories'] + df['category_name'].tolist()

@st.cache_data(ttl=3600)
def get_allergens():
    """Fetch all allergens for checkbox filter"""
    query = "SELECT allergen_id, name FROM allergens ORDER BY name"
    df = pd.read_sql(query, engine)
    return df

@st.cache_data(ttl=3600)
def get_diet_labels():
    """Fetch all diet labels for filter"""
    query = "SELECT label_id, label_name FROM diet_labels ORDER BY label_name"
    df = pd.read_sql(query, engine)
    return df

def search_recipes(cal_min, cal_max, carb_target, fat_target, prot_target, margin, 
                   category, exclude_allergen_ids, diet_label_ids):
    """Query recipes based on user filters"""
    
    # Allergen exclusion clause
    allergen_clause = ""
    if exclude_allergen_ids and len(exclude_allergen_ids) > 0:
        allergen_ids_str = ','.join(map(str, exclude_allergen_ids))
        allergen_clause = f"""
            AND NOT EXISTS (
                SELECT 1 FROM recipe_allergens ra
                WHERE ra.recipe_id = r.recipe_id
                AND ra.allergen_id IN ({allergen_ids_str})
            )
        """
    
    # Category clause
    category_clause = ""
    if category and category != 'All Categories':
        category_clause = f"AND LOWER(c.category_name) = LOWER('{category}')"
    
    # Diet label clause
    diet_clause = ""
    if diet_label_ids and len(diet_label_ids) > 0:
        label_ids_str = ','.join(map(str, diet_label_ids))
        diet_clause = f"""
            AND EXISTS (
                SELECT 1 FROM recipe_diet_labels rdl
                WHERE rdl.recipe_id = r.recipe_id
                AND rdl.label_id IN ({label_ids_str})
            )
        """
    
    # Main query
    query = f"""
    SELECT 
        v.recipe_id,
        v.name,
        v.url,
        v.calories,
        v.pct_carbs,
        v.pct_fat,
        v.pct_protein,
        c.category_name,
        r.rating
    FROM recipe_macro_pct v
    JOIN recipes r ON r.recipe_id = v.recipe_id
    LEFT JOIN categories c ON c.category_id = r.category_id
    WHERE v.calories BETWEEN {cal_min} AND {cal_max}
      AND v.pct_carbs BETWEEN {carb_target - margin} AND {carb_target + margin}
      AND v.pct_fat BETWEEN {fat_target - margin} AND {fat_target + margin}
      AND v.pct_protein BETWEEN {prot_target - margin} AND {prot_target + margin}
      {category_clause}
      {allergen_clause}
      {diet_clause}
    ORDER BY v.calories
    """
    
    try:
        df = pd.read_sql(query, engine)
        return df
    except Exception as e:
        st.error(f"Query failed: {e}")
        return pd.DataFrame()


# APP HEADER

st.title("Recipe Nutrition Filter")
st.markdown("""
Filter over 30,000 recipes by calorie range, macronutrient percentages, and dietary preferences.  
Set your targets and find recipes that match your nutrition goals!
""")

st.divider()

# SIDEBAR - INPUT CONTROLS

st.sidebar.header("Filter Settings")

# Calorie range filter (single dual-handle slider)
st.sidebar.subheader("Calorie Range")

cal_range = st.sidebar.slider(
    "Calories per Serving",
    min_value=100,
    max_value=1200,
    value=(100, 700),
    step=50
)

cal_min = cal_range[0]
cal_max = cal_range[1]

st.sidebar.divider()

st.sidebar.subheader("Macro Targets")

# Macro target sliders
carb_target = st.sidebar.slider(
    "Target Carbohydrate %",
    min_value=0,
    max_value=100,
    value=50,
    step=5
)

fat_target = st.sidebar.slider(
    "Target Fat %",
    min_value=0,
    max_value=100,
    value=30,
    step=5
)

prot_target = st.sidebar.slider(
    "Target Protein %",
    min_value=0,
    max_value=100,
    value=20,
    step=5
)

# Margin of error
margin = st.sidebar.slider(
    "Margin of Error (±%)",
    min_value=0,
    max_value=20,
    value=5,
    step=1
)

st.sidebar.divider()

# Category filter
st.sidebar.subheader("Category Filter")
categories = get_categories()
selected_category = st.sidebar.selectbox(
    "Select Category",
    options=categories,
    index=0
)

st.sidebar.divider()

# Diet label filter
st.sidebar.subheader("Diet Preferences")
diet_labels_df = get_diet_labels()
selected_diet_labels = st.sidebar.multiselect(
    "Include these diet types",
    options=diet_labels_df['label_name'].tolist(),
    help="Show only recipes matching these diet preferences"
)

# Convert selected diet label names to IDs
diet_label_ids = []
if selected_diet_labels:
    diet_label_ids = diet_labels_df[
        diet_labels_df['label_name'].isin(selected_diet_labels)
    ]['label_id'].tolist()

st.sidebar.divider()

# Allergen exclusion
st.sidebar.subheader("Exclude Allergens")
allergens_df = get_allergens()
exclude_allergens = st.sidebar.multiselect(
    "Exclude these allergens",
    options=allergens_df['name'].tolist()
)

# Convert selected allergen names to IDs
exclude_allergen_ids = []
if exclude_allergens:
    exclude_allergen_ids = allergens_df[
        allergens_df['name'].isin(exclude_allergens)
    ]['allergen_id'].tolist()


# MAIN CONTENT AREA

# Display current filter settings
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Calorie Range", f"{cal_min}-{cal_max} kcal")
with col2:
    st.metric("Carbs Target", f"{carb_target}% (±{margin}%)")
with col3:
    st.metric("Fat Target", f"{fat_target}% (±{margin}%)")

col4, col5, col6 = st.columns(3)
with col4:
    st.metric("Protein Target", f"{prot_target}% (±{margin}%)")
with col5:
    category_display = selected_category if selected_category != 'All Categories' else 'Any'
    st.metric("Category", category_display)
with col6:
    diet_display = f"{len(selected_diet_labels)} selected" if selected_diet_labels else "None"
    st.metric("Diet Preferences", diet_display)

st.divider()

# Execute search automatically on filter change
with st.spinner("Searching recipes..."):
    results_df = search_recipes(
        cal_min,
        cal_max, 
        carb_target, 
        fat_target, 
        prot_target, 
        margin,
        selected_category if selected_category != 'All Categories' else None,
        exclude_allergen_ids,
        diet_label_ids
    )

# Display results
if len(results_df) > 0:
    st.success(f"{len(results_df)} recipes match your criteria")
    
    # Prepare display dataframe
    display_df = results_df[[
        'name', 'calories', 'pct_carbs', 'pct_fat', 'pct_protein', 
        'category_name', 'rating', 'url'
    ]].copy()
    
    # Rename columns
    display_df.columns = [
        'Recipe Name', 'Calories', 'Carbs %', 'Fat %', 'Protein %', 
        'Category', 'Rating', 'URL'
    ]
    
    # Round numeric columns
    display_df['Carbs %'] = display_df['Carbs %'].round(1)
    display_df['Fat %'] = display_df['Fat %'].round(1)
    display_df['Protein %'] = display_df['Protein %'].round(1)
    display_df['Calories'] = display_df['Calories'].round(0).astype(int)
    display_df['Rating'] = display_df['Rating'].round(2)
    
    # Display as interactive table
    st.dataframe(
        display_df,
        column_config={
            "URL": st.column_config.LinkColumn(
                "Recipe Link",
                display_text="View Recipe"
            ),
            "Rating": st.column_config.NumberColumn(
                "Rating",
                format="%.2f"
            )
        },
        hide_index=True,
        use_container_width=True
    )
    
    # Download results
    csv = display_df.to_csv(index=False)
    st.download_button(
        label="Download Results as CSV",
        data=csv,
        file_name=f"recipe_results_{cal_min}-{cal_max}cal.csv",
        mime="text/csv"
    )
    
else:
    st.warning("No recipes found matching your criteria. Try adjusting your filters:")
    st.markdown("""
    - Increase the margin of error
    - Widen the calorie range
    - Remove diet preferences
    - Remove allergen exclusions
    - Select 'All Categories'
    """)


# FOOTER

st.divider()
st.caption("Disclaimer: This tool is for educational use only. All recipes and content belong to their respective authors and AllRecipes.com")