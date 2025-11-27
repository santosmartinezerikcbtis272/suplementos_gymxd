from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__, template_folder="suplementos_gym/templates")
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")


# ---------------------- CONEXIÓN A MONGO ATLAS ----------------------
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://santosmartinezerikcbtis272:1234@escuela.qjn2uo9.mongodb.net/?retryWrites=true&w=majority")

if not MONGO_URI:
    raise Exception("ERROR: No se encontró MONGO_URI en las variables de entorno.")

client = MongoClient(MONGO_URI)
db = client["suplementos_gym"]

productos_col = db["productos"]
usuarios_col = db["usuarios"]
pedidos_col = db["pedidos"]


# ---------------------- AUXILIARES ----------------------
def obtener_usuario():
    if "user" in session:
        usuario = usuarios_col.find_one({"_id": ObjectId(session["user"]["_id"])})
        if usuario:
            return usuario
        session.pop("user", None)
    return None


def obtener_productos():
    return list(productos_col.find())


def buscar_producto(producto_id):
    try:
        return productos_col.find_one({"_id": ObjectId(producto_id)})
    except:
        return None


def es_admin():
    user = obtener_usuario()
    return user and user.get("rol") == "admin"


# ---------------------- RUTAS PRINCIPALES ----------------------
@app.route("/")
def index():
    query = request.args.get("search", "")
    productos = obtener_productos()

    if query:
        productos = [p for p in productos if query.lower() in p["nombre"].lower()]

    return render_template(
        "index.html",
        productos=productos,
        user=session.get("user"),
        current_year=datetime.now().year,
    )


# ---------------------- REGISTRO ----------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nombre = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        if usuarios_col.find_one({"email": email}):
            return render_template("register.html", error="El correo ya está registrado")

        hashed = generate_password_hash(password)
        usuarios_col.insert_one(
            {
                "nombre": nombre,
                "email": email,
                "password": hashed,
                "cart": [],
                "rol": "user",
            }
        )
        return redirect(url_for("login"))

    return render_template("register.html")


# ---------------------- LOGIN ----------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = usuarios_col.find_one({"email": email})
        if user and check_password_hash(user["password"], password):
            session["user"] = {
                "_id": str(user["_id"]),
                "nombre": user["nombre"],
                "email": user["email"],
                "rol": user.get("rol", "user"),
            }
            return redirect(url_for("index"))

        return render_template("login.html", error="Credenciales incorrectas")

    return render_template("login.html")


# ---------------------- LOGOUT ----------------------
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))


# ---------------------- PRODUCTO DETALLE ----------------------
@app.route("/producto/<producto_id>")
def producto_detalle(producto_id):
    producto = buscar_producto(producto_id)
    recomendados = [p for p in obtener_productos() if str(p["_id"]) != producto_id]

    return render_template(
        "product.html",
        producto=producto,
        productos=recomendados,
        user=session.get("user"),
    )


# ---------------------- AGREGAR AL CARRITO ----------------------
@app.route("/agregar_carrito/<producto_id>", methods=["POST"])
def agregar_carrito(producto_id):
    user = obtener_usuario()
    if not user:
        return redirect(url_for("login"))

    cantidad = int(request.form.get("quantity", 1))
    carrito = user.get("cart", [])

    for item in carrito:
        if item["product_id"] == producto_id:
            item["quantity"] += cantidad
            break
    else:
        carrito.append({"product_id": producto_id, "quantity": cantidad})

    usuarios_col.update_one({"_id": user["_id"]}, {"$set": {"cart": carrito}})
    flash("Producto agregado al carrito 🛒", "success")
    return redirect(url_for("cart"))


# ---------------------- CARRITO ----------------------
@app.route("/cart")
def cart():
    user = obtener_usuario()
    if not user:
        return redirect(url_for("login"))

    cart_items = []
    total = 0

    for item in user.get("cart", []):
        producto = buscar_producto(item["product_id"])
        if producto:
            subtotal = producto["precio"] * item["quantity"]
            producto["quantity"] = item["quantity"]
            producto["subtotal"] = subtotal
            cart_items.append(producto)
            total += subtotal

    return render_template(
        "cart.html", cart_items=cart_items, total=total, user=session.get("user")
    )


# ---------------------- ACTUALIZAR CANTIDAD ----------------------
@app.route("/update_cart/<product_id>", methods=["POST"])
def update_cart(product_id):
    user = obtener_usuario()
    if not user:
        return redirect(url_for("login"))

    nueva_cantidad = int(request.form.get("quantity", 1))
    carrito = user.get("cart", [])

    for item in carrito:
        if item["product_id"] == product_id:
            item["quantity"] = nueva_cantidad
            break

    usuarios_col.update_one({"_id": user["_id"]}, {"$set": {"cart": carrito}})
    return redirect(url_for("cart"))


# ---------------------- ELIMINAR PRODUCTO ----------------------
@app.route("/remove_from_cart/<product_id>", methods=["POST"])
def remove_from_cart(product_id):
    user = obtener_usuario()
    if not user:
        return redirect(url_for("login"))

    carrito = [item for item in user.get("cart", []) if item["product_id"] != product_id]
    usuarios_col.update_one({"_id": user["_id"]}, {"$set": {"cart": carrito}})
    return redirect(url_for("cart"))


# ---------------------- CHECKOUT ----------------------
@app.route("/checkout")
def checkout():
    user = obtener_usuario()
    if not user:
        return redirect(url_for("login"))

    cart_items = []
    total = 0

    for item in user.get("cart", []):
        producto = buscar_producto(item["product_id"])
        if producto:
            subtotal = producto["precio"] * item["quantity"]
            producto["quantity"] = item["quantity"]
            producto["subtotal"] = subtotal
            cart_items.append(producto)
            total += subtotal

    return render_template(
        "checkout.html",
        productos=cart_items,
        cart_items=cart_items,
        total=total,
        user=session.get("user"),
    )


# ---------------------- CONFIRMAR PEDIDO — MODIFICADA ----------------------
@app.route("/confirm_order", methods=["POST"])
def confirm_order():
    user = obtener_usuario()
    if not user:
        return redirect(url_for("login"))

    nombre = request.form.get("nombre")
    direccion = request.form.get("direccion")
    metodo_pago = request.form.get("metodo_pago")

    cart_items = user.get("cart", [])
    if not cart_items:
        flash("Tu carrito está vacío.", "error")
        return redirect(url_for("cart"))

    total = sum(buscar_producto(item["product_id"])["precio"] * item["quantity"] for item in cart_items)

    pedidos_col.insert_one(
        {
            "user_id": user["_id"],
            "nombre": nombre,
            "direccion": direccion,
            "metodo_pago": metodo_pago,
            "productos": cart_items,
            "total": total,
            "fecha": datetime.now(),
        }
    )

    # Vaciar carrito
    usuarios_col.update_one({"_id": user["_id"]}, {"$set": {"cart": []}})

    # MENSAJE DE ÉXITO + REDIRECCIÓN AL MENÚ
    flash("🎉 ¡Compra realizada con éxito! Gracias por su pedido.", "success")
    return redirect(url_for("index"))


# ---------------------- ADMIN PANEL ----------------------
@app.route("/admin")
def admin_panel():
    if not es_admin():
        return redirect(url_for("index"))

    productos = obtener_productos()
    return render_template(
        "admin_panel.html", productos=productos, user=session.get("user")
    )


@app.route("/admin/agregar", methods=["GET", "POST"])
def admin_agregar_producto():
    if not es_admin():
        return redirect(url_for("index"))

    if request.method == "POST":
        productos_col.insert_one(
            {
                "nombre": request.form.get("nombre"),
                "precio": float(request.form.get("precio")),
                "categoria": request.form.get("categoria"),
                "stock": int(request.form.get("stock")),
                "descripcion": request.form.get("descripcion"),
                "imagen": request.form.get("imagen"),
            }
        )
        flash("Producto agregado correctamente", "success")
        return redirect(url_for("admin_panel"))

    return render_template("admin_agregar.html", user=session.get("user"))


# ---------------------- EJECUTAR APP ----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)

