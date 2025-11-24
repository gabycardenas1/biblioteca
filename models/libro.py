# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import requests

# =============================
# MODELO: LIBRO 
# =============================
class BibliotecaLibro(models.Model):
    _name = 'biblioteca.libro'
    _description = 'Libros de la Biblioteca'
    _rec_name = 'name'

    # ----------------------------
    # ESTADO GENERAL DEL REGISTRO
    # ----------------------------
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('saved', 'Guardado'),
        ('editing', 'Edición'),
        ('deleted', 'Eliminado')
    ], default='draft', string="Estado")

    # ----------------------------
    # CAMPOS PRINCIPALES
    # ----------------------------
    name = fields.Char(string='Nombre del libro')
    isbn = fields.Char(string='ISBN')
    autor = fields.Many2one('biblioteca.autor', string='Autor')
    categoria = fields.Char(string='Categoría')
    ubicacion = fields.Char(string='Ubicación física')

    # Inventario base
    ejemplares = fields.Integer(string='Ejemplares')

    # ----------------------------
    # DATOS DESDE OPENLIBRARY
    # ----------------------------
    description = fields.Text(string='Resumen')
    editorial = fields.Char(string='Editorial')
    paginas = fields.Integer(string='Páginas')
    fecha_publicacion = fields.Char(string='Fecha de Publicación')
    openlibrary_key = fields.Char(string='Open Library Key')

    # Relaciones antiguas (por si las usas en otros lados)
    prestamo_id = fields.Many2one('biblioteca.prestamo', string='Préstamo asociado')
    multa_id = fields.Many2one('biblioteca.multa', string='Multa asociada')

    # ----------------------------
    # CONTADORES DE INVENTARIO
    # ----------------------------
    ejemplares_disponibles = fields.Integer(
        string="Disponibles",
        compute="_compute_counters",
        store=False
    )
    ejemplares_prestados = fields.Integer(
        string="Prestados",
        compute="_compute_counters",
        store=False
    )
    ejemplares_en_multa = fields.Integer(
        string="En multa",
        compute="_compute_counters",
        store=False
    )

    @api.depends('ejemplares')
    def _compute_counters(self):
        """
        Calcula:
        - ejemplares_prestados: nro de préstamos con este libro en estado 'prestado'
        - ejemplares_en_multa: nro de préstamos con este libro en estado 'multa'
        - ejemplares_disponibles: ejemplares - prestados - en multa
        """
        Prestamo = self.env['biblioteca.prestamo']
        for r in self:
            if not r.id:
                r.ejemplares_prestados = 0
                r.ejemplares_en_multa = 0
                r.ejemplares_disponibles = r.ejemplares or 0
                continue

            prestados = Prestamo.search_count([
                ('libro_ids', 'in', r.id),
                ('estado', '=', 'prestado')
            ])

            en_multa = Prestamo.search_count([
                ('libro_ids', 'in', r.id),
                ('estado', '=', 'multa')
            ])

            r.ejemplares_prestados = prestados
            r.ejemplares_en_multa = en_multa
            r.ejemplares_disponibles = max((r.ejemplares or 0) - prestados - en_multa, 0)

    # =============================
    # BOTONES DE FLUJO
    # =============================
    def action_save_record(self):
        """Guardar y pasar a estado 'saved'."""
        for r in self:
            if r.ejemplares <= 0:
                r.ejemplares = 1  # mínimo 1 ejemplar si no puso nada
            r.state = 'saved'
        return True

    def action_edit(self):
        """Pasar a edición."""
        for r in self:
            r.state = 'editing'
        return True

    def action_discard(self):
        """Descartar cambios."""
        self.ensure_one()

        # Si es borrador (nuevo), limpiar todo
        if not self.id or self.state == 'draft':
            self.write({
                'name': False,
                'isbn': False,
                'autor': False,
                'ejemplares': 0,
                'description': False,
                'categoria': False,
                'ubicacion': False,
                'editorial': False,
                'paginas': 0,
                'fecha_publicacion': False,
                'openlibrary_key': False,
            })
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'biblioteca.libro',
                'view_mode': 'form',
                'target': 'current',
            }

        # Si estaba en edición, volver a guardado
        if self.state == 'editing':
            self.state = 'saved'

        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_delete_record(self):
        """Eliminar solo si no hay préstamos o multas asociadas."""
        self.ensure_one()
        if self.prestamo_id or self.multa_id:
            raise ValidationError(
                _("No se puede eliminar un libro que tiene préstamos o multas pendientes.")
            )
        return self.unlink()

    # =============================
    # API OPENLIBRARY
    # =============================
    def action_fill_book_data(self):
        """Botón que rellena datos desde OpenLibrary usando ISBN o nombre."""
        for r in self:
            # Limpiar datos antes de rellenar
            r.description = False
            r.editorial = False
            r.paginas = 0
            r.fecha_publicacion = False
            r.categoria = False
            r.openlibrary_key = False
            r.autor = False

            found = False

            if r.isbn:
                found = r._search_by_isbn()

            if not found and r.name:
                found = r._search_by_name()

            if not found:
                raise ValidationError(
                    _("No se pudieron encontrar datos para el libro en Open Library. "
                      "Verifique el ISBN o el Título.")
                )

            if r.state == 'saved':
                r.state = 'editing'

    # ----- AUXILIAR: DESCRIPCIÓN DESDE WORK -----
    def _get_description(self, olid):
        if not olid:
            return None

        url = f"https://openlibrary.org{olid}.json"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                desc = data.get('description')
                if isinstance(desc, dict):
                    desc = desc.get('value')
                return desc
        except Exception:
            return None
        return None

    # ----- BUSCAR POR ISBN -----
    def _search_by_isbn(self):
        self.ensure_one()
        if not self.isbn:
            return False

        url = f"https://openlibrary.org/isbn/{self.isbn}.json"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code != 200:
                return False

            data = res.json()

            self.name = data.get('title', self.name)
            publishers = data.get('publishers') or []
            if publishers:
                self.editorial = publishers[0]

            self.paginas = data.get('number_of_pages', 0)
            self.fecha_publicacion = data.get('publish_date', False)
            works = data.get('works') or []
            if works:
                self.openlibrary_key = works[0].get('key')

            if self.openlibrary_key:
                desc = self._get_description(self.openlibrary_key)
                if desc:
                    self.description = desc

            return True
        except Exception:
            return False

    # ----- BUSCAR POR NOMBRE -----
    def _search_by_name(self):
        self.ensure_one()
        if not self.name:
            return False

        name_q = self.name.replace(' ', '+')
        url = f"https://openlibrary.org/search.json?q={name_q}&limit=1"

        try:
            res = requests.get(url, timeout=10)
            if res.status_code != 200:
                return False

            data = res.json()
            if not data.get('docs'):
                return False

            doc = data['docs'][0]

            self.name = doc.get('title', self.name)
            self.openlibrary_key = doc.get('key')
            self.fecha_publicacion = doc.get('first_publish_year')
            publishers = doc.get('publisher') or []
            if publishers:
                self.editorial = publishers[0]
            self.paginas = doc.get('number_of_pages_median', 0)
            subjects = doc.get('subject') or []
            if subjects:
                self.categoria = subjects[0]

            # Tomar ISBN si no tiene
            isbns = doc.get('isbn') or []
            if isbns and not self.isbn:
                self.isbn = isbns[0]

            # Autor
            autores = doc.get('author_name') or []
            if autores:
                autor_nombre = autores[0]
                Autor = self.env['biblioteca.autor']
                autor_obj = Autor.search([('name', '=', autor_nombre)], limit=1)
                if not autor_obj:
                    autor_obj = Autor.create({'name': autor_nombre})
                self.autor = autor_obj.id

            # Descripción
            if self.openlibrary_key:
                desc = self._get_description(self.openlibrary_key)
                if desc:
                    self.description = desc

            return True

        except Exception:
            return False
