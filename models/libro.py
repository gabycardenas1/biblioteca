# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import requests

class BibliotecaLibro(models.Model):
    _name = 'biblioteca.libro'
    _description = 'Libros de la Biblioteca'
    _rec_name = 'name'

    # Estado
    state = fields.Selection([
        ('b', 'Borrador'),
        ('g', 'Guardado'),
        ('e', 'Edición'),
    ], default='b', string="Estado")

    # Campos principales
    name = fields.Char(string='Nombre del libro')
    isbn = fields.Char(string='ISBN')
    autor = fields.Many2one('biblioteca.autor', string='Autor')
    categoria = fields.Char(string='Categoría')
    ubicacion = fields.Char(string='Ubicación física')
    ejemplares = fields.Integer(string='Ejemplares')
    description = fields.Text(string='Resumen')
    editorial = fields.Char(string='Editorial')
    paginas = fields.Integer(string='Páginas')
    fecha_publicacion = fields.Char(string='Fecha de Publicación')
    openlibrary_key = fields.Char(string='Open Library Key')

    # Contadores
    ejemplares_disponibles = fields.Integer(compute="_compute_counters", store=True)
    ejemplares_prestados = fields.Integer(compute="_compute_counters", store=True)
    ejemplares_en_multa = fields.Integer(compute="_compute_counters", store=True)

    # Cálculo de contadores
    @api.depends('ejemplares')
    def _compute_counters(self):
        Prestamo = self.env['biblioteca.prestamo']
        for libro in self:
            libro.ejemplares_prestados = Prestamo.search_count([
                ('libro_ids', 'in', libro.id),
                ('estado', '=', 'prestado')
            ])
            libro.ejemplares_en_multa = Prestamo.search_count([
                ('libro_ids', 'in', libro.id),
                ('estado', '=', 'multa')
            ])
            libro.ejemplares_disponibles = max(
                (libro.ejemplares or 0)
                - libro.ejemplares_prestados
                - libro.ejemplares_en_multa,
                0
            )

    # Guardar
    def guardarLibro(self):
        for libro in self:
            if libro.ejemplares <= 0:
                libro.ejemplares = 1
            libro.state = 'g'
        return True

    # Editar
    def editarLibro(self):
        for libro in self:
            if libro.state == 'g':
                libro.state = 'e'
        return True

    # Búsqueda general
    def buscarLibro(self):
        for libro in self:
            encontrado = False
            if libro.isbn:
                encontrado = libro.buscarPorIsbn()
            if not encontrado and libro.name:
                encontrado = libro.buscarPorTitulo()
            if not encontrado:
                raise ValidationError(_("No se encontraron datos en OpenLibrary."))
        return True

    # Buscar por ISBN
    def buscarPorIsbn(self):
        self.ensure_one()
        url = f"https://openlibrary.org/isbn/{self.isbn}.json"

        try:
            respuesta = requests.get(url, timeout=10)
            if respuesta.status_code != 200:
                return False

            datos = respuesta.json()

            # Título
            self.name = datos.get("title") or self.name

            # Editorial
            publishers = datos.get("publishers") or []
            if publishers:
                self.editorial = publishers[0]

            # Páginas
            paginas = datos.get("number_of_pages") or datos.get("number_of_pages_median")
            if paginas:
                self.paginas = paginas

            # Año
            if datos.get("publish_date"):
                self.fecha_publicacion = datos["publish_date"]

            # WORK
            works = datos.get("works") or []
            if works:
                workKey = works[0].get("key")
                self.openlibrary_key = workKey

                # Descripción
                descripcion = self.obtenerDescripcion(workKey)
                if descripcion:
                    self.description = descripcion

                # Categoría
                detalles = self.obtenerWork(workKey)
                if detalles:
                    subjects = detalles.get("subjects") or []
                    if subjects:
                        self.categoria = subjects[0]

            # Autor
            autores = datos.get("authors") or []
            if autores:
                self.cargarAutorDesdeKey(autores[0].get("key"))

            return True

        except Exception:
            return False

    # Buscar por título
    def buscarPorTitulo(self):
        self.ensure_one()
        titulo = self.name.replace(" ", "+")
        url = f"https://openlibrary.org/search.json?q={titulo}&limit=1"

        try:
            respuesta = requests.get(url, timeout=10)
            if respuesta.status_code != 200:
                return False

            docs = respuesta.json().get("docs")
            if not docs:
                return False

            libroData = docs[0]

            # Título
            self.name = libroData.get("title") or self.name

            # Editorial
            publishers = libroData.get("publisher") or []
            if publishers:
                self.editorial = publishers[0]

            # Año
            if libroData.get("first_publish_year"):
                self.fecha_publicacion = str(libroData["first_publish_year"])

            # Páginas
            paginas = libroData.get("number_of_pages_median")
            if paginas:
                self.paginas = paginas

            # ISBN sugerido
            isbns = libroData.get("isbn") or []
            if isbns and not self.isbn:
                self.isbn = isbns[0]

            # Autor
            autores = libroData.get("author_name") or []
            if autores:
                self.guardarAutor(autores[0])

            # WORK KEY
            workKey = libroData.get("key")

            # Normalizar: asegurar que sea un /works/ válido
            if workKey and not workKey.startswith("/works/"):
                workId = workKey.split("/")[-1]
                workKey = f"/works/{workId}"

            # Cargar WORK
            if workKey and workKey.startswith("/works/"):
                self.openlibrary_key = workKey
                detalles = self.obtenerWork(workKey)

                if detalles:
                    subjects = detalles.get("subjects") or []
                    if subjects:
                        self.categoria = subjects[0]

                    descripcion = detalles.get("description")
                    if isinstance(descripcion, dict):
                        self.description = descripcion.get("value")
                    elif isinstance(descripcion, str):
                        self.description = descripcion

            return True

        except Exception:
            return False

    # Obtener WORK
    def obtenerWork(self, workKey):
        if not workKey:
            return None
        try:
            respuesta = requests.get(f"https://openlibrary.org{workKey}.json", timeout=10)
            if respuesta.status_code != 200:
                return None
            return respuesta.json()
        except:
            return None

    # Cargar autor desde clave
    def cargarAutorDesdeKey(self, authorKey):
        if not authorKey:
            return
        try:
            respuesta = requests.get(f"https://openlibrary.org{authorKey}.json", timeout=10)
            if respuesta.status_code != 200:
                return
            datos = respuesta.json()
            nombre = datos.get("name")
            if not nombre:
                return

            Autor = self.env["biblioteca.autor"]
            autor = Autor.search([("name", "=", nombre)], limit=1)
            if not autor:
                autor = Autor.create({"name": nombre})

            self.autor = autor.id
        except:
            return

    # Guardar autor por nombre
    def guardarAutor(self, nombre):
        Autor = self.env["biblioteca.autor"]
        autor = Autor.search([("name", "=", nombre)], limit=1)
        if not autor:
            autor = Autor.create({"name": nombre})
        self.autor = autor.id