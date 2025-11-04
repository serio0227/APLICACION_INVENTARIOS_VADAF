import streamlit as st
import sqlite3
import pandas as pd
import io
from datetime import datetime, timedelta

# --- Configuración de la Página ---
st.set_page_config(
    page_title="Inventario VADAF",
    page_icon="👟",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Nombre de la Base de Datos ---
DB_NAME = "vadaf_inventory.db"

# --- Funciones de Estilo (CSS) ---
def load_css():
    """Carga el CSS personalizado para el estilo profesional y limpio (blanco)."""
    st.markdown("""
    <style>
        /* Paleta de colores VADAF (Profesional/Blanco) */
        :root {
            --primary-color: #007bff; /* Azul profesional */
            --secondary-color: #f8f9fa; /* Fondo gris muy claro */
            --accent-color: #0056b3; /* Azul más oscuro (hover) */
            --text-color: #ffffff; /* Texto sobre primario (botones) */
            --dark-text: #212529; /* Texto principal oscuro */
            --light-border: #dee2e6; /* Borde claro */
            --danger-color: #d32f2f; /* Rojo crítico */
            --warning-color: #fbc02d; /* Amarillo bajo */
            --success-color: #388e3c; /* Verde óptimo */
        }

        /* Fuente y Fondo general */
        .stApp {
            background-color: var(--secondary-color);
            color: var(--dark-text);
        }
        
        /* Ajuste de fuente base */
        body, .stApp, .stTextInput, .stNumberInput, .stSelectbox {
            font-size: 16px;
        }

        /* Barra lateral */
        [data-testid="stSidebar"] {
            background-color: #ffffff;
            border-right: 1px solid var(--light-border);
        }
        [data-testid="stSidebar"] .stRadio > label,
        [data-testid="stSidebar"] .stMarkdown {
            color: var(--dark-text);
        }
        [data-testid="stSidebar"] h1 {
            color: var(--primary-color);
            font-size: 26px;
            text-align: center;
        }

        /* Botones principales */
        .stButton > button {
            background-color: var(--primary-color);
            color: var(--text-color);
            border: none;
            padding: 10px 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            font-weight: bold;
        }
        .stButton > button:hover {
            background-color: var(--accent-color);
            color: var(--text-color);
        }

        /* Botón de peligro (Eliminar) */
        .stButton > button[kind="secondary"] {
            background-color: var(--danger-color);
            color: var(--text-color);
        }
        .stButton > button[kind="secondary"]:hover {
            background-color: #b71c1c;
        }

        /* Formularios, expanders y contenedores (Tarjetas blancas) */
        [data-testid="stForm"], [data-testid="stExpander"], .st-container,
        [data-testid="stDataFrame"], [data-testid="stMetric"] {
            background-color: #ffffff;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.05);
            border: 1px solid var(--light-border);
        }
        
        /* Títulos */
        h1, h2 {
            color: var(--primary-color);
        }
        h3 {
             color: var(--dark-text);
        }
        
        /* Etiquetas de formulario más legibles */
        [data-testid="stTextInput"] label, 
        [data-testid="stNumberInput"] label, 
        [data-testid="stSelectbox"] label, 
        [data-testid="stTextArea"] label, 
        .stRadio > label {
            font-size: 1.05rem;
            font-weight: 500;
            color: #333;
        }
        
        /* Alertas de stock */
        .stock-critical { color: var(--danger-color); font-weight: bold; }
        .stock-low { color: var(--warning-color); font-weight: bold; }
        .stock-ok { color: var(--success-color); font-weight: bold; }

        /* Estilo de Tarjetas KPI para el dashboard */
        [data-testid="stVerticalBlock"] > div:nth-child(1) .stMarkdown {
            padding: 10px 15px;
            border-radius: 8px;
            margin-bottom: 10px;
        }
    </style>
    """, unsafe_allow_html=True)

# --- Funciones de Base de Datos (SQLite) ---

def get_db_connection():
    """Establece conexión con la base de datos SQLite."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Inicializa las tablas de la base de datos si no existen."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabla de Proveedores (Debe ir antes que Productos si hay FK)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        nit TEXT UNIQUE,
        contact_person TEXT,
        email TEXT,
        avg_delivery_time_days INTEGER
    )
    """)
    
    # Tabla de Productos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        category TEXT NOT NULL CHECK(category IN ('Materia Prima', 'Producto en Proceso', 'Producto Terminado')),
        shoe_type TEXT,
        size TEXT,
        color TEXT,
        quantity INTEGER NOT NULL DEFAULT 0,
        min_stock INTEGER NOT NULL DEFAULT 10,
        location TEXT,
        supplier_id INTEGER,
        unit_cost REAL NOT NULL DEFAULT 0,
        FOREIGN KEY (supplier_id) REFERENCES suppliers (id)
    )
    """)
    
    # Tabla de Movimientos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        type TEXT NOT NULL CHECK(type IN ('Entrada', 'Salida')),
        quantity INTEGER NOT NULL,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        notes TEXT,
        FOREIGN KEY (product_id) REFERENCES products (id)
    )
    """)
    
    conn.commit()
    conn.close()

# --- Funciones CRUD (Productos, Proveedores, Movimientos) ---

def db_fetch(query, params=()):
    """Ejecuta una consulta SELECT y devuelve un DataFrame."""
    conn = get_db_connection()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def db_execute(query, params=()):
    """Ejecuta una consulta INSERT, UPDATE o DELETE."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        conn.close()
        return True, None
    except sqlite3.Error as e:
        return False, str(e)

# --- Funciones de las Páginas ---

def show_dashboard():
    """Muestra el panel principal (Tablero de control) estilo Power BI."""
    st.title("👟 Dashboard Analítico de Inventarios VADAF")
    
    # --- Cargar Datos Principales ---
    df_products = db_fetch("SELECT * FROM products")
    df_movements = db_fetch("SELECT * FROM movements ORDER BY date DESC")
    
    if df_products.empty:
        st.info("No hay productos en el inventario. Agregue productos en 'Gestión de Productos'.")
        return

    # Preparación de datos (KPIs y Estados)
    df_products['Valor_Total'] = df_products['quantity'] * df_products['unit_cost']
    df_products['stock_status'] = df_products.apply(
        lambda row: 'Crítico' if row['quantity'] < row['min_stock'] 
                    else ('Bajo' if row['quantity'] <= row['min_stock'] * 1.2 
                          else 'Óptimo'), 
        axis=1
    )
    
    # 1. FILTROS INTERACTIVOS (Sidebar)
    with st.sidebar:
        st.subheader("Filtros del Dashboard")
        all_categories = df_products['category'].unique().tolist()
        selected_categories = st.multiselect(
            "Filtrar por Categoría", 
            options=all_categories, 
            default=all_categories
        )

    df_filtered = df_products[df_products['category'].isin(selected_categories)]
    
    # Verificar si el filtro ha dejado el DF vacío
    if df_filtered.empty:
        st.warning("No hay datos para las categorías seleccionadas.")
        return

    # --- 2. TARJETAS DE MÉTRICAS (KPIs) ---
    st.header("Métricas Clave (KPIs)")
    
    total_items = df_filtered['quantity'].sum()
    total_value = df_filtered['Valor_Total'].sum()
    low_stock_count = len(df_filtered[df_filtered['stock_status'].isin(['Crítico', 'Bajo'])])

    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.container()
        st.info("Valor Total Inventario")
        st.markdown(f"## **${total_value:,.0f}**")
        
    with col2:
        st.container()
        st.info("Total Unidades")
        st.markdown(f"## **{total_items:,}**")

    with col3:
        st.container()
        st.warning("SKUs con Bajo Stock")
        st.markdown(f"## **{low_stock_count}**")
        
    with col4:
        st.container()
        avg_cost = df_filtered['unit_cost'].mean() if not df_filtered['unit_cost'].empty else 0
        st.success("Costo Promedio Unitario")
        st.markdown(f"## **${avg_cost:,.2f}**")

    st.markdown("---")

    # --- 3. GRÁFICOS ANALÍTICOS Y VISUALIZACIONES ---
    st.header("Análisis de Existencias y Valor")

    c1, c2 = st.columns(2)
    
    # Gráfico 1: Stock por Categoría (Cantidad)
    with c1:
        st.subheader("1. Stock por Categoría (Unidades)")
        stock_by_cat = df_filtered.groupby('category')['quantity'].sum().sort_values(ascending=False)
        st.bar_chart(stock_by_cat, color="#007bff")

    # Gráfico 2: Valor por Categoría
    with c2:
        st.subheader("2. Valor por Categoría ($)")
        stock_value_by_cat = df_filtered.groupby('category')['Valor_Total'].sum().sort_values(ascending=False)
        st.bar_chart(stock_value_by_cat, color="#0056b3")
        
    st.markdown("---")

    # Gráfico 3: Productos Críticos (Tabla/Gráfico)
    st.subheader("3. Top 10 Productos con Stock Crítico")
    low_stock_products = df_filtered[df_filtered['stock_status'].isin(['Crítico', 'Bajo'])].sort_values(by='quantity').head(10)
    
    if low_stock_products.empty:
        st.success("No hay productos en estado Crítico/Bajo en las categorías seleccionadas.")
    else:
        # Usamos un gráfico horizontal para mejor visualización de ranking
        low_stock_products_chart = low_stock_products.set_index('name')['quantity']
        low_stock_products_chart.name = "Unidades Actuales"
        st.bar_chart(low_stock_products_chart, color="#d32f2f") # 


    # Gráfico 4: Movimientos Históricos (Interactivo)
    if not df_movements.empty:
        st.markdown("---")
        st.subheader("4. Tendencia de Movimientos de Inventario (Últimos 30 días)")
        
        # Filtro de fecha predeterminado: 30 días
        df_movements['date'] = pd.to_datetime(df_movements['date'])
        start_date = datetime.now() - timedelta(days=30)
        df_movements_filtered = df_movements[df_movements['date'] >= start_date].copy()
        
        if not df_movements_filtered.empty:
            # Agrupar por día
            df_movements_filtered['day'] = df_movements_filtered['date'].dt.date
            
            # Pivotear para tener Entradas y Salidas en columnas separadas
            df_pivot = df_movements_filtered.pivot_table(
                index='day', 
                columns='type', 
                values='quantity', 
                aggfunc='sum'
            ).fillna(0)
            
            # Crear gráfico de líneas
            st.line_chart(df_pivot, use_container_width=True, color=["#388e3c", "#d32f2f"]) # Entrada (Verde), Salida (Rojo)
        else:
            st.info("No hay movimientos registrados en los últimos 30 días para estas categorías.")


def manage_products():
    """Página para la gestión (CRUD) de productos."""
    st.title("📦 Gestión de Productos: Crear, Editar y Eliminar")
    
    df_suppliers = db_fetch("SELECT id, name FROM suppliers")
    supplier_dict = pd.Series(df_suppliers['id'].values, index=df_suppliers['name']).to_dict()
    supplier_names = ['Ninguno'] + list(supplier_dict.keys())
    
    categories = ['Materia Prima', 'Producto en Proceso', 'Producto Terminado']

    # --- Formulario para Agregar (Ventana Emergente Simulado) ---
    with st.expander("➕ Crear Nuevo Producto", expanded=False):
        st.subheader("Datos de Creación Rápida")
        with st.form("new_product_form", clear_on_submit=True):
            
            # Col 1: Información básica
            col1_1, col1_2, col1_3 = st.columns(3)
            code = col1_1.text_input("Código (SKU) *", help="Debe ser único.")
            name = col1_2.text_input("Nombre del Producto *")
            category = col1_3.selectbox("Categoría *", categories)
            
            # Col 2: Especificaciones
            col2_1, col2_2, col2_3 = st.columns(3)
            shoe_type = col2_1.text_input("Tipo de Zapato")
            size = col2_2.text_input("Talla/Medida")
            color = col2_3.text_input("Color")
            
            # Col 3: Stock y Costo
            col3_1, col3_2, col3_3 = st.columns(3)
            quantity = col3_1.number_input("Cantidad Inicial *", min_value=0, step=1)
            min_stock = col3_2.number_input("Stock Mínimo (Alerta) *", min_value=0, step=1, value=10)
            unit_cost = col3_3.number_input("Costo Unitario/Producción *", min_value=0.0, format="%.2f")
            
            # Col 4: Ubicación y Proveedor
            col4_1, col4_2 = st.columns(2)
            location = col4_1.text_input("Ubicación en Almacén")
            supplier_name = col4_2.selectbox("Proveedor", supplier_names)
            
            submitted = st.form_submit_button("✅ Guardar Producto", type="primary")
            
            if submitted:
                # Validación
                if not code or not name or not category or quantity is None or min_stock is None or unit_cost is None:
                    st.error("Por favor complete todos los campos obligatorios (*).")
                else:
                    supplier_id_to_use = supplier_dict.get(supplier_name)
                    success, error = db_execute(
                        """
                        INSERT INTO products (code, name, category, shoe_type, size, color, quantity, min_stock, location, supplier_id, unit_cost)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (code, name, category, shoe_type, size, color, quantity, min_stock, location, supplier_id_to_use, unit_cost)
                    )
                    if success:
                        st.success(f"Producto '{name}' agregado exitosamente.")
                        st.rerun()
                    else:
                        if "UNIQUE constraint failed" in error:
                            st.error(f"Error: El código '{code}' ya existe. Use un código único.")
                        else:
                            st.error(f"Error al guardar: {error}")

    st.markdown("---")

    # --- Vista, Edición y Eliminación de Productos ---
    st.subheader("Inventario Actual: Edición Rápida y Eliminación")
    
    # Cargar datos
    query = """
    SELECT 
        p.id, p.code, p.name, p.category, p.quantity, p.min_stock, p.unit_cost,
        p.shoe_type, p.size, p.color, p.location, s.name AS supplier_name
    FROM products p
    LEFT JOIN suppliers s ON p.supplier_id = s.id
    ORDER BY p.name
    """
    df_products = db_fetch(query)

    if df_products.empty:
        st.info("Aún no hay productos registrados.")
        return

    # --- Filtros ---
    col_search, col_filter = st.columns([2, 1])
    search_term = col_search.text_input("Buscar por Nombre o Código")
    filter_category = col_filter.multiselect("Filtrar por Categoría", options=categories, default=categories)
    
    filtered_df = df_products[
        (df_products['name'].str.contains(search_term, case=False, na=False) | 
         df_products['code'].str.contains(search_term, case=False, na=False)) &
        (df_products['category'].isin(filter_category))
    ].copy() 
    
    # Agregar columna para eliminación
    filtered_df['Eliminar'] = False

    # --- Mostrar Tabla (Editable) ---
    st.info("Edite las columnas Nombre, Categoría, Cantidad, Stock Mínimo, Costo Unitario y detalles directamente. Marque 'Eliminar' para borrar filas.")
    
    # Columnas editables y configuradas
    column_config = {
        "id": st.column_config.NumberColumn("ID", disabled=True),
        "code": st.column_config.TextColumn("Código", disabled=True),
        "name": st.column_config.TextColumn("Nombre", required=True),
        "category": st.column_config.SelectboxColumn("Categoría", options=categories, required=True),
        "quantity": st.column_config.NumberColumn("Cantidad", min_value=0, step=1, required=True),
        "min_stock": st.column_config.NumberColumn("Stock Mínimo", min_value=0, step=1, required=True),
        "unit_cost": st.column_config.NumberColumn("Costo Unitario", min_value=0.0, format="%.2f", required=True),
        "shoe_type": st.column_config.TextColumn("Tipo Zapato"),
        "size": st.column_config.TextColumn("Talla"),
        "color": st.column_config.TextColumn("Color"),
        "location": st.column_config.TextColumn("Ubicación"),
        "supplier_name": st.column_config.TextColumn("Proveedor", disabled=True),
        "Eliminar": st.column_config.CheckboxColumn("🗑️ Eliminar?", default=False),
    }

    # Usar st.data_editor para edición en vivo
    edited_data = st.data_editor(
        filtered_df,
        column_config=column_config,
        hide_index=True,
        use_container_width=True,
    )
    
    # --- Lógica de Guardado y Eliminación de st.data_editor ---
    
    if st.button("💾 Guardar Cambios y Procesar Eliminaciones", type="primary"):
        st.subheader("Procesando Cambios...")
        
        # 1. Procesar Eliminaciones
        items_to_delete = edited_data[edited_data['Eliminar'] == True]
        if not items_to_delete.empty:
            st.warning(f"Se eliminarán {len(items_to_delete)} producto(s).")
            for index, row in items_to_delete.iterrows():
                success, error = db_execute("DELETE FROM products WHERE id = ?", (row['id'],))
                if success:
                    st.success(f"Producto '{row['name']}' (ID: {row['id']}) ELIMINADO.")
                else:
                    st.error(f"Error al eliminar '{row['name']}': {error}")
        
        # 2. Procesar Ediciones (Solo los que NO están marcados para eliminar)
        items_to_update = edited_data[edited_data['Eliminar'] == False]
        
        updated_count = 0
        for index, new_row in items_to_update.iterrows():
            original_row = df_products[df_products['id'] == new_row['id']].iloc[0]
            
            # Verificar si algún campo editable ha cambiado
            is_modified = (
                original_row['name'] != new_row['name'] or
                original_row['category'] != new_row['category'] or
                original_row['quantity'] != new_row['quantity'] or
                original_row['min_stock'] != new_row['min_stock'] or
                original_row['unit_cost'] != new_row['unit_cost'] or
                original_row['shoe_type'] != new_row['shoe_type'] or
                original_row['size'] != new_row['size'] or
                original_row['color'] != new_row['color'] or
                original_row['location'] != new_row['location']
            )

            if is_modified:
                success, error = db_execute(
                    """
                    UPDATE products SET 
                        name = ?, category = ?, quantity = ?, min_stock = ?, unit_cost = ?,
                        shoe_type = ?, size = ?, color = ?, location = ?
                    WHERE id = ?
                    """,
                    (
                        new_row['name'], new_row['category'], new_row['quantity'], 
                        new_row['min_stock'], new_row['unit_cost'], new_row['shoe_type'], 
                        new_row['size'], new_row['color'], new_row['location'], new_row['id']
                    )
                )
                if success:
                    updated_count += 1
                else:
                    st.error(f"Error al actualizar '{new_row['name']}': {error}")

        if updated_count > 0 or not items_to_delete.empty:
            st.success(f"Se procesaron {updated_count} actualizaciones y {len(items_to_delete)} eliminaciones.")
            st.rerun()
        
        if items_to_delete.empty and updated_count == 0:
            st.info("No se detectaron cambios ni eliminaciones por procesar.")


def manage_movements():
    """Página para registrar entradas y salidas de inventario, actualizando el stock en tiempo real."""
    st.title("🚚 Gestión de Movimientos: Entradas y Salidas")
    st.info("Registrar un movimiento aquí actualiza el stock del producto de forma inmediata.")
    
    df_products = db_fetch("SELECT id, name, code, quantity FROM products")
    if df_products.empty:
        st.warning("No hay productos registrados. No se pueden registrar movimientos.")
        return

    product_dict = pd.Series(df_products['id'].values, index=df_products['name']).to_dict()
    product_names = list(product_dict.keys())

    # --- Formulario de Registro (Interactividad) ---
    with st.form("movement_form", clear_on_submit=True):
        st.subheader("Registrar Nueva Transacción")
        
        c1, c2 = st.columns(2)
        product_name = c1.selectbox("Producto *", product_names, key="move_product")
        movement_type = c2.radio("Tipo de Movimiento *", ['Entrada', 'Salida'], key="move_type")
        
        current_stock_row = df_products[df_products['name'] == product_name]
        current_stock = current_stock_row['quantity'].iloc[0] if not current_stock_row.empty else 0
        
        st.markdown(f"**Stock Actual de {product_name}:** `{current_stock}`")

        quantity = st.number_input("Cantidad *", min_value=1, step=1, key="move_qty")
        notes = st.text_area("Observaciones (Ej: Venta #123, Devolución de Cliente, Compra a Proveedor X)", key="move_notes")
        
        submitted = st.form_submit_button("Registrar y Actualizar Stock", type="primary")
        
        if submitted:
            product_id = product_dict[product_name]
            
            # Validación de Stock (solo para Salida)
            if movement_type == 'Salida' and quantity > current_stock:
                st.error(f"⚠️ Error: Stock insuficiente para '{product_name}'. Stock actual: {current_stock}")
            else:
                # 1. Registrar el movimiento
                success, error = db_execute(
                    "INSERT INTO movements (product_id, type, quantity, notes) VALUES (?, ?, ?, ?)",
                    (product_id, movement_type, quantity, notes)
                )
                
                if success:
                    # 2. Actualizar el stock del producto
                    if movement_type == 'Entrada':
                        new_stock = current_stock + quantity
                    else: # Salida
                        new_stock = current_stock - quantity
                    
                    success_update, error_update = db_execute(
                        "UPDATE products SET quantity = ? WHERE id = ?",
                        (new_stock, product_id)
                    )
                    
                    if success_update:
                        st.success(f"Movimiento '{movement_type}' de {quantity} unidad(es) de '{product_name}' registrado.")
                        st.balloons()
                        st.rerun() # Recargar para reflejar el nuevo stock
                    else:
                        st.error(f"Error al actualizar stock: {error_update}. Contacte al administrador.")
                else:
                    st.error(f"Error al registrar movimiento: {error}")

    st.markdown("---")
    
    # --- Historial de Movimientos ---
    st.subheader("Historial de Movimientos Recientes")
    query = """
    SELECT m.date, p.name, p.code, m.type, m.quantity, m.notes
    FROM movements m
    JOIN products p ON m.product_id = p.id
    ORDER BY m.date DESC
    LIMIT 100
    """
    df_movements = db_fetch(query)
    
    # Aplicar colores para diferenciar
    def style_movements(row):
        if row['type'] == 'Entrada':
            return ['background-color: #e8f5e9; color: #388e3c'] * len(row) # Verde claro
        elif row['type'] == 'Salida':
            return ['background-color: #ffebee; color: #d32f2f'] * len(row) # Rojo claro
        return [''] * len(row)

    st.dataframe(
        df_movements.style.apply(style_movements, axis=1), 
        use_container_width=True
    )


def manage_suppliers():
    """Página para la gestión (CRUD COMPLETO) de proveedores."""
    st.title("🏭 Gestión de Proveedores (CRUD Completo)")
    
    df_suppliers = db_fetch("SELECT * FROM suppliers")
    
    # --- Formulario de Agregar (Ventana Emergente Simulado) ---
    with st.expander("➕ Crear Nuevo Proveedor", expanded=False):
        st.subheader("Datos de Creación Rápida")
        with st.form("add_supplier_form", clear_on_submit=True):
            
            c1, c2 = st.columns(2)
            name = c1.text_input("Nombre / Razón Social *")
            nit = c2.text_input("NIT o Identificación (Único)")
            
            c3, c4 = st.columns(2)
            contact_person = c3.text_input("Persona de Contacto")
            email = c4.text_input("Correo Electrónico")
            
            avg_delivery_time_days = st.number_input("Tiempo de Entrega Promedio (días)", min_value=0, step=1)
            
            submitted = st.form_submit_button("✅ Guardar Proveedor", type="primary")
            
            if submitted:
                if not name:
                    st.error("El nombre del proveedor es obligatorio.")
                else:
                    success, error = db_execute(
                        "INSERT INTO suppliers (name, nit, contact_person, email, avg_delivery_time_days) VALUES (?, ?, ?, ?, ?)",
                        (name, nit, contact_person, email, avg_delivery_time_days)
                    )
                    if success:
                        st.success(f"Proveedor '{name}' agregado exitosamente.")
                        st.rerun()
                    else:
                        if "UNIQUE constraint failed" in error:
                            st.error(f"Error: El NIT '{nit}' ya está registrado.")
                        else:
                            st.error(f"Error al guardar: {error}")
    
    st.markdown("---")
    
    # --- Lista, Edición y Eliminación ---
    st.subheader("Lista, Edición y Eliminación de Proveedores")
    
    if df_suppliers.empty:
        st.info("Aún no hay proveedores registrados.")
        return

    # Selector para Edición/Eliminación
    supplier_names = df_suppliers['name'].tolist()
    supplier_selection = st.selectbox("Seleccione el Proveedor a Editar/Eliminar", supplier_names)
    
    if supplier_selection:
        selected_supplier = df_suppliers[df_suppliers['name'] == supplier_selection].iloc[0]
        supplier_id = selected_supplier['id']

        # --- Formulario de Edición (Simulado Pop-up) ---
        with st.expander(f"✍️ Editar Detalles de: {supplier_selection}", expanded=True):
            with st.form("edit_supplier_form", clear_on_submit=False):
                
                col_e1, col_e2 = st.columns(2)
                edit_name = col_e1.text_input("Nombre / Razón Social *", value=selected_supplier['name'], key="e_name")
                edit_nit = col_e2.text_input("NIT o Identificación", value=selected_supplier['nit'], key="e_nit")
                
                col_e3, col_e4 = st.columns(2)
                edit_contact_person = col_e3.text_input("Persona de Contacto", value=selected_supplier['contact_person'], key="e_contact")
                edit_email = col_e4.text_input("Correo Electrónico", value=selected_supplier['email'], key="e_email")
                
                edit_avg_delivery = st.number_input("Tiempo de Entrega Promedio (días)", min_value=0, step=1, 
                                                    value=int(selected_supplier['avg_delivery_time_days'] or 0), key="e_avg_days")
                
                update_submitted = st.form_submit_button("Actualizar Detalles", type="primary")
                
                if update_submitted:
                    if not edit_name:
                        st.error("El nombre del proveedor es obligatorio.")
                    else:
                        success, error = db_execute(
                            """
                            UPDATE suppliers SET name = ?, nit = ?, contact_person = ?, email = ?, avg_delivery_time_days = ?
                            WHERE id = ?
                            """,
                            (edit_name, edit_nit, edit_contact_person, edit_email, edit_avg_delivery, supplier_id)
                        )
                        if success:
                            st.success(f"Proveedor '{edit_name}' actualizado exitosamente.")
                            st.rerun()
                        else:
                            st.error(f"Error al actualizar: {error}")
                            
            # Botón de eliminación (fuera del formulario, dentro del expander de acción)
            st.markdown("---")
            st.warning("Zona de peligro: la eliminación es permanente.")
            if st.button(f"🗑️ Eliminar Proveedor: {supplier_selection}", type="secondary"):
                # Antes de eliminar, verificar si hay productos asociados
                products_count_df = db_fetch("SELECT COUNT(*) as count FROM products WHERE supplier_id = ?", (supplier_id,))
                products_count = products_count_df['count'].iloc[0] if not products_count_df.empty else 0
                
                if products_count > 0:
                    st.error(f"❌ Error: No se puede eliminar. Este proveedor está asociado a {products_count} producto(s). Primero debe editar esos productos y asignarles otro proveedor o eliminarlos.")
                else:
                    success, error = db_execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
                    if success:
                        st.success(f"Proveedor '{supplier_selection}' eliminado exitosamente.")
                        st.rerun()
                    else:
                        st.error(f"Error al eliminar: {error}")
                        
        st.markdown("---")
    
    # Mostrar la lista completa (después de la edición/eliminación)
    df_updated_suppliers = db_fetch("SELECT * FROM suppliers")
    st.dataframe(df_updated_suppliers, use_container_width=True)


def show_reports():
    """Página para generar y descargar reportes, con opción CSV/Excel y filtros."""
    st.title("📊 Generación de Reportes")
    
    report_type = st.selectbox(
        "Seleccione el tipo de reporte:",
        ["Existencias Actuales", "Valor Total del Inventario", "Movimientos Históricos"]
    )
    
    df_report = pd.DataFrame()
    
    if report_type == "Existencias Actuales":
        st.subheader("Reporte de Existencias Actuales")
        query = """
        SELECT 
            p.code AS 'Código', p.name AS 'Nombre', p.category AS 'Categoría',
            p.quantity AS 'Cantidad', p.min_stock AS 'Stock Mínimo', p.location AS 'Ubicación',
            s.name AS 'Proveedor', p.unit_cost AS 'Costo Unitario'
        FROM products p
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        ORDER BY p.name
        """
        df_report = db_fetch(query)
        st.dataframe(df_report, use_container_width=True) 
    
    elif report_type == "Valor Total del Inventario":
        st.subheader("Reporte de Valor Total del Inventario")
        query = """
        SELECT
            p.code AS 'Código', p.name AS 'Nombre', p.category AS 'Categoría',
            p.quantity AS 'Cantidad', p.unit_cost AS 'Costo Unitario',
            (p.quantity * p.unit_cost) AS 'Valor Total'
        FROM products p
        ORDER BY "Valor Total" DESC
        """
        df_report = db_fetch(query)
        
        # Añadir fila de total para la visualización
        total_value = df_report['Valor Total'].sum()
        total_row = pd.DataFrame({
            'Código': ['---'], 'Nombre': ['---'], 'Categoría': ['---'],
            'Cantidad': ['---'], 'Costo Unitario': ['**TOTAL**'], 
            'Valor Total': [f"**{total_value:,.2f}**"]
        })
        # Solo para mostrar, el DF para exportar (df_report) no incluye esta fila.
        df_display = pd.concat([df_report.astype(str), total_row], ignore_index=True)
        st.dataframe(df_display, use_container_width=True)

    elif report_type == "Movimientos Históricos":
        st.subheader("Reporte de Movimientos Históricos (Filtro por Fecha)")
        
        # Filtro de fecha
        col_start, col_end = st.columns(2)
        default_start = datetime.now().replace(day=1) 
        default_end = datetime.now()
        
        start_date = col_start.date_input("Fecha Inicio", value=default_start)
        end_date = col_end.date_input("Fecha Fin", value=default_end)
        
        # Convertir a string para la consulta SQLite
        start_str = start_date.strftime('%Y-%m-%d 00:00:00')
        end_str = end_date.strftime('%Y-%m-%d 23:59:59')
        
        query = f"""
        SELECT 
            strftime('%Y-%m-%d %H:%M', m.date) AS 'Fecha',
            p.name AS 'Producto', p.code AS 'Código',
            m.type AS 'Tipo', m.quantity AS 'Cantidad',
            m.notes AS 'Observaciones'
        FROM movements m
        JOIN products p ON m.product_id = p.id
        WHERE m.date BETWEEN '{start_str}' AND '{end_str}'
        ORDER BY m.date DESC
        """
        df_report = db_fetch(query)
        st.dataframe(df_report, use_container_width=True) 

    # --- Botones de Descarga ---
    if not df_report.empty:
        st.markdown("---")
        
        col_excel, col_csv = st.columns(2)

        # Descargar Excel 
        output_excel = io.BytesIO()
        try:
            with pd.ExcelWriter(output_excel, engine='xlsxwriter') as writer: 
                df_report.to_excel(writer, index=False, sheet_name='Reporte')
            
            col_excel.download_button(
                label="📄 Descargar Reporte (Excel)",
                data=output_excel.getvalue(),
                file_name=f"reporte_vadaf_{report_type.lower().replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except ImportError:
            col_excel.info("Instale 'openpyxl' o 'xlsxwriter' (`pip install xlsxwriter`) para la descarga a Excel.")

        # Descargar CSV
        csv = df_report.to_csv(index=False).encode('utf-8')
        col_csv.download_button(
            label="📄 Descargar Reporte (CSV)",
            data=csv,
            file_name=f"reporte_vadaf_{report_type.lower().replace(' ', '_')}.csv",
            mime="text/csv",
        )
        
        st.markdown("---")
        if st.button("🖨️ Imprimir Reporte (Simulación)"):
            st.info("La función de impresión directa no está soportada. Por favor, use la función de impresión de su navegador (Ctrl+P) o descargue el Excel/CSV.")

# --- Lógica Principal (Main) ---

def run_main_app():
    """Ejecuta la aplicación principal."""
    load_css()
    
    # --- Barra Lateral (Menú) ---
    with st.sidebar:
        st.title("VADAF 👟")
        st.markdown("Gestor de Inventarios")
        st.markdown("---")
        
        menu_options = [
            "Panel Principal", 
            "Gestión de Productos", 
            "Gestión de Movimientos", 
            "Gestión de Proveedores",
            "Generación de Reportes"
        ]

        if 'menu_selection' not in st.session_state:
            st.session_state.menu_selection = "Panel Principal"

        menu_selection = st.radio("Menú Principal", menu_options, key="menu_selection_widget")
        st.session_state.menu_selection = menu_selection
        
    # --- Enrutador de Páginas ---
    if st.session_state.menu_selection == "Panel Principal":
        show_dashboard()
    elif st.session_state.menu_selection == "Gestión de Productos":
        manage_products()
    elif st.session_state.menu_selection == "Gestión de Movimientos":
        manage_movements()
    elif st.session_state.menu_selection == "Gestión de Proveedores":
        manage_suppliers()
    elif st.session_state.menu_selection == "Generación de Reportes":
        show_reports()

# --- Punto de Entrada de la Aplicación ---
if __name__ == "__main__":
    init_db() 
    run_main_app() 

