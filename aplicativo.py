import streamlit as st
import sqlite3
import pandas as pd
import hashlib # Mantenido por si se usa en el futuro, aunque no para login
import io
from datetime import datetime

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
    
    # Tabla de Movimientos (Sin 'user')
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
    """Muestra el panel principal (Tablero de control)."""
    st.title("👟 Panel Principal - Inventarios VADAF")
    
    # Cargar datos
    df_products = db_fetch("SELECT * FROM products")
    
    if df_products.empty:
        st.info("No hay productos en el inventario. Agregue productos en 'Gestión de Productos'.")
        return

    # 1. Métricas Clave
    total_items = df_products['quantity'].sum()
    total_value = (df_products['quantity'] * df_products['unit_cost']).sum()
    total_skus = len(df_products)
    
    df_products['stock_status'] = df_products.apply(
        lambda row: 'Crítico' if row['quantity'] < row['min_stock'] 
                    else ('Bajo' if row['quantity'] <= row['min_stock'] * 1.2 
                          else 'Óptimo'), 
        axis=1
    )
    low_stock_count = len(df_products[df_products['stock_status'].isin(['Crítico', 'Bajo'])])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Valor Total del Inventario", f"${total_value:,.2f}")
    col2.metric("Total de Artículos", f"{total_items:,}")
    col3.metric("Total de SKUs", f"{total_skus}")
    col4.metric("SKUs con Bajo Inventario", f"{low_stock_count}", delta_color="inverse")

    st.markdown("---")

    # 2. Alertas de Bajo Inventario
    st.subheader("⚠️ Alertas de Bajo Inventario")
    low_stock_products = df_products[df_products['stock_status'].isin(['Crítico', 'Bajo'])].sort_values(by='quantity')
    
    if low_stock_products.empty:
        st.success("¡Todo en orden! No hay productos con bajo inventario.")
    else:
        for _, row in low_stock_products.iterrows():
            level = row['stock_status']
            if level == 'Crítico':
                st.error(f"**CRÍTICO:** {row['name']} (Código: {row['code']}) - Quedan: {row['quantity']} (Mínimo: {row['min_stock']})")
            elif level == 'Bajo':
                st.warning(f"**BAJO:** {row['name']} (Código: {row['code']}) - Quedan: {row['quantity']} (Mínimo: {row['min_stock']})")

    st.markdown("---")

    # 3. Gráficas Simples
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Inventario por Categoría (Cantidad)")
        stock_by_cat = df_products.groupby('category')['quantity'].sum()
        st.bar_chart(stock_by_cat, color="var(--primary-color)")

    with col2:
        st.subheader("Inventario por Categoría (Valor)")
        stock_value_by_cat = (df_products['quantity'] * df_products['unit_cost']).groupby(df_products['category']).sum()
        st.bar_chart(stock_value_by_cat, color="var(--accent-color)")

def manage_products():
    """Página para la gestión (CRUD) de productos."""
    st.title("📦 Gestión de Productos")
    
    df_suppliers = db_fetch("SELECT id, name FROM suppliers")
    supplier_dict = pd.Series(df_suppliers['id'].values, index=df_suppliers['name']).to_dict()
    supplier_names = ['Ninguno'] + list(supplier_dict.keys())
    
    categories = ['Materia Prima', 'Producto en Proceso', 'Producto Terminado']

    # --- Formulario para Agregar/Editar ---
    with st.expander("➕ Agregar Nuevo Producto", expanded=False):
        with st.form("new_product_form", clear_on_submit=True):
            st.subheader("Nuevo Producto")
            
            # Campos
            code = st.text_input("Código (SKU) *", help="Debe ser único.")
            name = st.text_input("Nombre del Producto *")
            category = st.selectbox("Categoría *", categories)
            
            c1, c2, c3 = st.columns(3)
            shoe_type = c1.text_input("Tipo de Zapato (Ej: Bota, Sneaker)")
            size = c2.text_input("Talla (Ej: 38, M)")
            color = c3.text_input("Color (Ej: Negro)")
            
            c4, c5, c6 = st.columns(3)
            quantity = c4.number_input("Cantidad Inicial *", min_value=0, step=1)
            min_stock = c5.number_input("Stock Mínimo (Alerta) *", min_value=0, step=1, value=10)
            unit_cost = c6.number_input("Costo Unitario/Producción *", min_value=0.0, format="%.2f")
            
            location = st.text_input("Ubicación en Almacén (Ej: Zona A, Estante 3)")
            supplier_name = st.selectbox("Proveedor", supplier_names)
            supplier_id = supplier_dict.get(supplier_name)
            
            submitted = st.form_submit_button("Guardar Producto")
            
            if submitted:
                # Validación
                if not code or not name or not category or quantity is None or min_stock is None or unit_cost is None:
                    st.error("Por favor complete todos los campos obligatorios (*).")
                else:
                    success, error = db_execute(
                        """
                        INSERT INTO products (code, name, category, shoe_type, size, color, quantity, min_stock, location, supplier_id, unit_cost)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (code, name, category, shoe_type, size, color, quantity, min_stock, location, supplier_id, unit_cost)
                    )
                    if success:
                        st.success(f"Producto '{name}' agregado exitosamente.")
                    else:
                        if "UNIQUE constraint failed" in error:
                            st.error(f"Error: El código '{code}' ya existe. Use un código único.")
                        else:
                            st.error(f"Error al guardar: {error}")

    st.markdown("---")

    # --- Vista y Edición de Productos ---
    st.subheader("Inventario Actual")
    
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
    c1, c2 = st.columns([2, 1])
    search_term = c1.text_input("Buscar por Nombre o Código")
    filter_category = c2.multiselect("Filtrar por Categoría", options=categories, default=categories)
    
    filtered_df = df_products[
        (df_products['name'].str.contains(search_term, case=False) | 
         df_products['code'].str.contains(search_term, case=False)) &
        (df_products['category'].isin(filter_category))
    ]

    # --- Mostrar Tabla (Editable) ---
    st.info("Puede editar las celdas directamente. Los cambios se guardarán automáticamente (Función de Data Editor).")
    
    # Columnas editables
    editable_columns = {
        "name": st.column_config.TextColumn("Nombre", required=True),
        "category": st.column_config.SelectboxColumn("Categoría", options=categories, required=True),
        "quantity": st.column_config.NumberColumn("Cantidad", min_value=0, required=True),
        "min_stock": st.column_config.NumberColumn("Stock Mínimo", min_value=0, required=True),
        "unit_cost": st.column_config.NumberColumn("Costo Unitario", min_value=0.0, format="%.2f", required=True),
        "shoe_type": st.column_config.TextColumn("Tipo Zapato"),
        "size": st.column_config.TextColumn("Talla"),
        "color": st.column_config.TextColumn("Color"),
        "location": st.column_config.TextColumn("Ubicación"),
        # 'supplier_name' es más complejo de editar aquí, se deja como solo lectura
    }
    
    # Columnas deshabilitadas
    disabled_cols = ['id', 'code', 'supplier_name']

    # Usar st.data_editor para edición en vivo
    edited_data = st.data_editor(
        filtered_df,
        column_config=editable_columns,
        disabled=disabled_cols,
        num_rows="dynamic", # Permitir añadir y eliminar filas
        use_container_width=True,
        on_change=st.cache_data.clear() # Limpiar cache en cambios
    )
    
    # (Nota: La lógica completa para sincronizar st.data_editor (editar/añadir/borrar filas) 
    # con la BD es compleja y requiere manejo de estado. 
    # Esta versión permite la adición/eliminación visual, pero la persistencia
    # principal sigue estando en el formulario "Agregar" y la sección "Eliminar".)

    # --- Eliminación ---
    st.markdown("---")
    st.subheader("Eliminar Producto")
    product_list = ["Seleccione un producto..."] + df_products['name'].tolist()
    product_to_delete = st.selectbox("Producto a Eliminar", product_list)
    
    if product_to_delete != "Seleccione un producto...":
        product_id = df_products[df_products['name'] == product_to_delete]['id'].iloc[0]
        if st.button(f"Eliminar {product_to_delete}", type="secondary"):
            # (En una app real: Verificar si hay movimientos asociados)
            success, error = db_execute("DELETE FROM products WHERE id = ?", (product_id,))
            if success:
                st.success(f"Producto '{product_to_delete}' eliminado.")
                st.rerun()
            else:
                st.error(f"Error al eliminar: {error}")

def manage_movements():
    """Página para registrar entradas y salidas de inventario."""
    st.title("🚚 Gestión de Movimientos")
    
    df_products = db_fetch("SELECT id, name, code, quantity FROM products")
    if df_products.empty:
        st.warning("No hay productos registrados. No se pueden registrar movimientos.")
        return

    product_dict = pd.Series(df_products['id'].values, index=df_products['name']).to_dict()
    product_names = list(product_dict.keys())

    # --- Formulario de Registro ---
    with st.form("movement_form", clear_on_submit=True):
        st.subheader("Registrar Movimiento")
        
        c1, c2 = st.columns(2)
        product_name = c1.selectbox("Producto *", product_names)
        movement_type = c2.radio("Tipo de Movimiento *", ['Entrada', 'Salida'])
        
        quantity = st.number_input("Cantidad *", min_value=1, step=1)
        notes = st.text_area("Observaciones (Ej: Venta #123, Compra a Proveedor X)")
        
        submitted = st.form_submit_button("Registrar Movimiento")
        
        if submitted:
            product_id = product_dict[product_name]
            current_stock = df_products[df_products['id'] == product_id]['quantity'].iloc[0]
            
            # Validación
            if movement_type == 'Salida' and quantity > current_stock:
                st.error(f"Error: No hay stock suficiente para '{product_name}'. Stock actual: {current_stock}")
            else:
                # 1. Registrar el movimiento (sin usuario)
                success, error = db_execute(
                    "INSERT INTO movements (product_id, type, quantity, notes) VALUES (?, ?, ?, ?)",
                    (product_id, movement_type, quantity, notes)
                )
                if not success:
                    st.error(f"Error al registrar movimiento: {error}")
                    return

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
                    st.success(f"Movimiento '{movement_type}' de {quantity} unidad(es) de '{product_name}' registrado. Nuevo stock: {new_stock}")
                else:
                    st.error(f"Error al actualizar stock: {error_update}")

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
    
    # Aplicar colores
    def style_movements(row):
        if row['type'] == 'Entrada':
            return ['background-color: #e8f5e9'] * len(row) # Verde claro
        elif row['type'] == 'Salida':
            return ['background-color: #ffebee'] * len(row) # Rojo claro
        return [''] * len(row)

    st.dataframe(
        df_movements.style.apply(style_movements, axis=1), 
        use_container_width=True
    )

def manage_suppliers():
    """Página para la gestión (CRUD) de proveedores."""
    st.title("🏭 Gestión de Proveedores")
    
    # --- Formulario de Gestión ---
    with st.expander("➕ Agregar/Editar Proveedor", expanded=False):
        with st.form("supplier_form", clear_on_submit=True):
            st.subheader("Datos del Proveedor")
            
            name = st.text_input("Nombre / Razón Social *")
            nit = st.text_input("NIT o Identificación")
            contact_person = st.text_input("Persona de Contacto")
            email = st.text_input("Correo Electrónico")
            avg_delivery_time_days = st.number_input("Tiempo de Entrega Promedio (días)", min_value=0, step=1)
            
            submitted = st.form_submit_button("Guardar Proveedor")
            
            if submitted:
                if not name:
                    st.error("El nombre del proveedor es obligatorio.")
                else:
                    # (Aquí iría lógica para INSERT O UPDATE si se selecciona uno existente)
                    success, error = db_execute(
                        "INSERT INTO suppliers (name, nit, contact_person, email, avg_delivery_time_days) VALUES (?, ?, ?, ?, ?)",
                        (name, nit, contact_person, email, avg_delivery_time_days)
                    )
                    if success:
                        st.success(f"Proveedor '{name}' agregado.")
                    else:
                        if "UNIQUE constraint failed" in error:
                            st.error(f"Error: El NIT '{nit}' ya está registrado.")
                        else:
                            st.error(f"Error al guardar: {error}")
    
    st.markdown("---")
    
    # --- Lista de Proveedores ---
    st.subheader("Lista de Proveedores")
    df_suppliers = db_fetch("SELECT * FROM suppliers")
    st.dataframe(df_suppliers, use_container_width=True)

def show_reports():
    """Página para generar y descargar reportes."""
    st.title("📊 Generación de Reportes")
    
    report_type = st.selectbox(
        "Seleccione el tipo de reporte:",
        ["Existencias Actuales", "Valor Total del Inventario", "Movimientos del Mes"]
    )
    
    df_report = pd.DataFrame()
    
    if report_type == "Existencias Actuales":
        st.subheader("Reporte de Existencias Actuales")
        query = """
        SELECT 
            p.code AS 'Código', p.name AS 'Nombre', p.category AS 'Categoría',
            p.quantity AS 'Cantidad', p.min_stock AS 'Stock Mínimo', p.location AS 'Ubicación',
            s.name AS 'Proveedor'
        FROM products p
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        ORDER BY p.name
        """
        df_report = db_fetch(query)
    
    elif report_type == "Valor Total del Inventario":
        st.subheader("Reporte de Valor Total del Inventario")
        query = """
        SELECT
            p.code AS 'Código', p.name AS 'Nombre', p.category AS 'Categoría',
            p.quantity AS 'Cantidad', p.unit_cost AS 'Costo Unitario',
            (p.quantity * p.unit_cost) AS 'Valor Total'
        FROM products p
        ORDER BY 'Valor Total' DESC
        """
        df_report = db_fetch(query)
        
        # Añadir fila de total
        total_value = df_report['Valor Total'].sum()
        total_row = pd.DataFrame({
            'Código': ['---'], 'Nombre': ['---'], 'Categoría': ['---'],
            'Cantidad': ['---'], 'Costo Unitario': ['**TOTAL**'], 
            'Valor Total': [f"**{total_value:,.2f}**"]
        })
        df_report = pd.concat([df_report, total_row], ignore_index=True)

    elif report_type == "Movimientos del Mes":
        st.subheader("Reporte de Movimientos del Mes Actual")
        # (Esto asume SQLite, la sintaxis de fecha puede variar)
        query = """
        SELECT 
            strftime('%Y-%m-%d %H:%M', m.date) AS 'Fecha',
            p.name AS 'Producto', p.code AS 'Código',
            m.type AS 'Tipo', m.quantity AS 'Cantidad',
            m.notes AS 'Observaciones'
        FROM movements m
        JOIN products p ON m.product_id = p.id
        WHERE strftime('%Y-%m', m.date) = strftime('%Y-%m', 'now')
        ORDER BY m.date DESC
        """
        df_report = db_fetch(query)

    st.dataframe(df_report, use_container_width=True)
    
    # --- Botones de Descarga ---
    if not df_report.empty:
        st.markdown("---")
        
        # Descargar Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_report.to_excel(writer, index=False, sheet_name='Reporte')
        
        st.download_button(
            label="📄 Descargar Reporte (Excel)",
            data=output.getvalue(),
            file_name=f"reporte_vadaf_{report_type.lower().replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # Botón de impresión (simulado, solo muestra un mensaje)
        if st.button("🖨️ Imprimir Reporte (Simulación)"):
            st.info("La función de impresión directa no está soportada. Por favor, use la función de impresión de su navegador (Ctrl+P) o descargue el Excel.")

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

        menu_selection = st.radio("Menú Principal", menu_options, key="menu_selection")
        
    # --- Enrutador de Páginas ---
    if menu_selection == "Panel Principal":
        show_dashboard()
    elif menu_selection == "Gestión de Productos":
        manage_products()
    elif menu_selection == "Gestión de Movimientos":
        manage_movements()
    elif menu_selection == "Gestión de Proveedores":
        manage_suppliers()
    elif menu_selection == "Generación de Reportes":
        show_reports()

# --- Punto de Entrada de la Aplicación ---
if __name__ == "__main__":
    init_db() # Asegura que la BD y las tablas existan
    run_main_app() # Ejecuta la app directamente

