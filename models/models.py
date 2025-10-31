# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import requests

# =============================
# MODELO: LIBRO 
# =============================
class Biblioteca(models.Model):
    _name = 'biblioteca.libro'
    _description = 'biblioteca.biblioteca'
    _rec_name = 'name'

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('saved', 'Guardado'),
        ('editing', 'Edición'),
        ('deleted', 'Eliminado')
    ], string='Estado', default='draft')

    name = fields.Char(string='Nombre libro')
    isbn = fields.Char(string='ISBN', placeholder='Ingrese el código ISBN')
    autor = fields.Many2one('biblioteca.autor', string='Autor del libro')
    ejemplares = fields.Integer(string='Número de ejemplares')
    costo = fields.Float(compute="_value_pc", store=True, string='Costo')
    description = fields.Text(string='Resumen del libro')
    categoria = fields.Char(string="Categoría")
    ubicacion = fields.Char(string='Ubicación física')
    prestamo_id = fields.Many2one('biblioteca.prestamo', string='Préstamo asociado')
    multa_id = fields.Many2one('biblioteca.multa', string='Multa asociada')
    readonly_after_prestado = fields.Boolean(string='Readonly after prestado', default=False)
    editorial = fields.Char(string='Editorial')
    paginas = fields.Integer(string='Páginas')
    fecha_publicacion = fields.Char(string='Fecha de Publicación')
    openlibrary_key = fields.Char(string='Open Library Key', readonly=True)

    @api.depends('ejemplares')
    def _value_pc(self):
        for record in self:
            record.costo = (record.ejemplares or 0) * 1.5
            
    # ----------------------------------------------------
    # FUNCIONES DE FLUJO
    # ----------------------------------------------------

    def action_save_record(self):
        for record in self:
            record.write({'state': 'saved'})
        return True
    
    def action_edit(self):
        for record in self:
            record.state = 'editing'
        return True

    def action_discard(self):
        self.ensure_one()
        
        # Caso 1: Si está en Borrador (registro nuevo, id=False), limpia los campos.
        if not self.id or self.state == 'draft':
            self.write({
                'name': False, 'isbn': False, 'autor': False, 'ejemplares': 0, 'description': False, 
                'categoria': False, 'ubicacion': False, 'editorial': False, 'paginas': 0, 
                'fecha_publicacion': False, 'openlibrary_key': False
            })
            return {
                            'type': 'ir.actions.act_window',
                            'res_model': 'biblioteca.libro',
                            'view_mode': 'form',
                            'views': [(False, 'form')],
                            'target': 'current',
                        }
            
        # Caso 2: Si está en Edición, vuelve a Guardado y revierte los cambios
        if self.state == 'editing':
            self.state = 'saved'
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }


    def action_delete_record(self):
        self.ensure_one()
        if self.prestamo_id or self.multa_id:
            raise ValidationError(_("No se puede eliminar un libro que tiene préstamos o multas pendientes."))
        return self.unlink()

    def action_fill_book_data(self):
        for record in self:
            record.description = False
            record.editorial = False
            record.paginas = 0
            record.fecha_publicacion = False
            record.categoria = False
            record.openlibrary_key = False
            record.autor = False
            
            found = False
            if record.isbn:
                found = record._search_by_isbn()
            if not found and record.name:
                found = record._search_by_name()
            if not found:
                raise ValidationError(_("No se pudieron encontrar datos para el libro."))
            if record.state == 'saved':
                 record.state = 'editing'

    # FUNCIONES AUXILIARES DE LA API
    # ----------------------------------------------------
    
    def _get_description_and_image(self, olid):
        if not olid:
            return {}
            
        url = f"https://openlibrary.org{olid}.json"
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                description = data.get('description')
                if isinstance(description, dict) and 'value' in description:
                    description = description['value']
                    
                return {'description': description}
            return {}
        except Exception:
            return {}


    def _search_by_isbn(self):
        self.ensure_one()
        if not self.isbn:
            return False
        
        url = f"https://openlibrary.org/isbn/{self.isbn}.json"
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                self.name = data.get('title', self.name)
                
                publishers = data.get('publishers')
                if isinstance(publishers, list) and publishers:
                    self.editorial = publishers[0]
                
                self.paginas = data.get('number_of_pages', 0)
                self.fecha_publicacion = data.get('publish_date', False)
                self.openlibrary_key = data.get('works', [{}])[0].get('key', False) 

                if self.openlibrary_key:
                    desc_data = self._get_description_and_image(self.openlibrary_key)
                    if desc_data.get('description'):
                        self.description = desc_data['description']
                
                return True
            return False
        except Exception:
            return False


    def _search_by_name(self):
        self.ensure_one()
        if not self.name:
            return False

        nombre_formateado = self.name.replace(' ', '+')
        url = f"https://openlibrary.org/search.json?q={nombre_formateado}&limit=1"
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                if data and 'docs' in data and data['docs']:
                    primer_resultado = data['docs'][0]
                    
                    self.name = primer_resultado.get('title', self.name)
                    self.openlibrary_key = primer_resultado.get('key', False)
                    isbns = primer_resultado.get('isbn', [])
                    if isbns and not self.isbn:
                        self.isbn = isbns[0]
                        
                    subjects = primer_resultado.get('subject', [])
                    if subjects:
                        self.categoria = subjects[0]
                    self.fecha_publicacion = primer_resultado.get('first_publish_year', False)
                    
                    publishers = primer_resultado.get('publisher')
                    if isinstance(publishers, list) and publishers:
                        self.editorial = publishers[0]
                    
                    self.paginas = primer_resultado.get('number_of_pages_median', 0)

                    autores = primer_resultado.get('author_name', [])
                    if autores:
                        autor_nombre = autores[0]
                        autor_obj = self.env['biblioteca.autor'].search([('firstname', '=', autor_nombre)], limit=1)
                        if not autor_obj:
                            autor_obj = self.env['biblioteca.autor'].create({'firstname': autor_nombre})
                        self.autor = autor_obj.id

                    if self.openlibrary_key:
                        desc_data = self._get_description_and_image(self.openlibrary_key)
                        if desc_data.get('description'):
                            self.description = desc_data['description']

                    return True
                return False
            return False
        except Exception:
            return False

    # ACCIÓN PRINCIPAL LLAMADA DESDE EL BOTÓN XML 
    # ----------------------------------------------------
    
    def action_fill_book_data(self):
        for record in self:
            record.description = False
            record.editorial = False
            record.paginas = 0
            record.fecha_publicacion = False
            record.categoria = False
            record.openlibrary_key = False
            record.autor = False
            
            found = False
            
            if record.isbn:
                found = record._search_by_isbn()
            
            if not found and record.name:
                found = record._search_by_name()
            
            if not found:
                raise ValidationError(_("No se pudieron encontrar datos para el libro en Open Library. Intente verificar el ISBN o el Título."))

    # FUNCIÓN DE ELIMINAR 
    # ----------------------------------------------------
    
    def action_delete_record(self):
        """Elimina el registro de la base de datos."""
        self.ensure_one()
        if self.prestamo_id or self.multa_id:
            raise ValidationError(_("No se puede eliminar un libro que tiene préstamos o multas pendientes."))
            
        return self.unlink()
    
    
    
# =============================
# MODELO: AUTOR
# =============================
class BibliotecaAutor(models.Model):
    _name = 'biblioteca.autor'
    _description = 'Registro de autores'
    _rec_name = 'firstname'
    
    firstname = fields.Char(string='Nombre')
    lastname = fields.Char(string='Apellido')


# =============================
# MODELO: USUARIO
# =============================
class BibliotecaUsuario(models.Model):
    _name = 'biblioteca.usuarios'
    _description = 'Usuarios de la biblioteca'
    _rec_name = 'nombre_completo'
    
    nombre_completo = fields.Char(string='Nombre completo', required=True)
    cedula = fields.Char(string='Cédula o ID', required=True)
    correo = fields.Char(string='Correo electrónico')
    telefono = fields.Char(string='Teléfono')
    direccion = fields.Char(string='Dirección')
    fecha_registro = fields.Datetime(string='Fecha de registro', default=fields.Datetime.now)
    prestamo_ids = fields.One2many('biblioteca.prestamo', 'usuario_id', string='Préstamos realizados')
    multa_ids = fields.One2many('biblioteca.multa', 'usuario_id', string='Multas registradas')

    @api.constrains('cedula')
    def _check_cedula(self):
        for record in self:
            if record.cedula and not self.validar_cedula_ecuatoriana(record.cedula):
                raise ValidationError(_("La cédula ingresada no es válida."))

    def validar_cedula_ecuatoriana(self, cedula):
        if not cedula or len(cedula) != 10 or not cedula.isdigit():
            return False
        provincia = int(cedula[:2])
        if provincia < 1 or provincia > 24:
            return False
        tercer_digito = int(cedula[2])
        if tercer_digito >= 6:
            return False
        coeficientes = [2,1,2,1,2,1,2,1,2]
        suma = 0
        for i in range(9):
            valor = int(cedula[i]) * coeficientes[i]
            if valor >= 10:
                valor -= 9
            suma += valor
        verificador = int(cedula[9])
        decena_superior = ((suma + 9) // 10) * 10
        return verificador == (decena_superior - suma) % 10


# =============================
# MODELO: PERSONAL
# =============================
class BibliotecaPersonal(models.Model):
    _name = 'biblioteca.personal'
    _description = 'Personal de la biblioteca'

    name = fields.Char(string='Nombre completo')
    codigo = fields.Char(string='Código interno', required=True)


# =============================
# MODELO: MULTA
# =============================
class BibliotecaMulta(models.Model):
    _name = 'biblioteca.multa'
    _description = 'Registro de multas'
    _rec_name = 'name_multa'

    name_multa = fields.Char(string='Código de multa')
    fecha_prestamo = fields.Datetime(string='Fecha de préstamo')
    libro_id = fields.One2many('biblioteca.libro', 'multa_id', string='Libro asociado')
    usuario_id = fields.Many2one('biblioteca.usuarios', string='Usuario')
    fecha_devolucion = fields.Datetime(string='Fecha de devolución')


# =============================
# MODELO: PRESTAMO
# =============================
class BibliotecaPrestamo(models.Model):
    _name = 'biblioteca.prestamo'
    _description = 'Registro de préstamos de la biblioteca'

    name = fields.Char(string='Nombre')
    fecha_prestamo = fields.Datetime(string='Fecha de préstamo')
    fecha_max_devolucion = fields.Datetime(string='Fecha máxima de devolución', readonly=True)
    fecha_devolucion = fields.Datetime(string='Fecha de devolución')
    libro_id = fields.One2many('biblioteca.libro', 'prestamo_id', string='Libro')
    usuario_id = fields.Many2one('biblioteca.usuarios', string='Usuarios')
    personal_id = fields.Many2one('biblioteca.personal', string='Personal que presta')
    estado = fields.Selection([
    ('borrador', 'Borrador'),
    ('prestado', 'Prestado'),
    ('devuelto', 'Devuelto'),
    ('multa', 'Multa')], string='Estado', default='borrador')
    multa_bol = fields.Boolean(default=False)
    multa = fields.Float()
    multa_diaria = fields.Float(default=5.0, string='Multa por día')

    # ----------------------
    # Botón para prestar
    # ----------------------
    def action_prestar(self):
        if not self.usuario_id or not self.personal_id or not self.libro_id:
            raise ValidationError(_("Debe asignar usuario, personal y libro(s) antes de prestar."))
        self.fecha_prestamo = datetime.now()
        self.fecha_max_devolucion = self.fecha_prestamo + timedelta(days=15)
        self.estado = 'prestado'
        for libro in self.libro_id:
            libro.write({'prestamo_id': self.id, 'readonly_after_prestado': True})

    # ----------------------
    # Botón para devolver
    # ----------------------
    def action_devolver(self):
        self.fecha_devolucion = datetime.now()
        self.estado = 'devuelto'
        self.calcular_multa()

    # ----------------------
    # Calcular multas
    # ----------------------
    def calcular_multa(self):
        for record in self:
            if record.fecha_max_devolucion:
                if record.fecha_devolucion:
                    retraso = (record.fecha_devolucion - record.fecha_max_devolucion).days
                else:
                    retraso = (datetime.now() - record.fecha_max_devolucion).days
                record.multa = record.multa_diaria * max(retraso,0)
                record.multa_bol = record.multa > 0
