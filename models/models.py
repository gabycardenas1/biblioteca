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

    @api.depends('ejemplares')
    def _value_pc(self):
        for record in self:
            record.costo = (record.ejemplares or 0) * 1.5

    def consultar_api_openlibrary(self):
        for record in self:
            if not record.isbn:
                raise ValidationError(_("Debe ingresar un ISBN antes de consultar la API."))
            url = f"https://openlibrary.org/isbn/{record.isbn}.json"
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    record.name = data.get('title', record.name)
                    record.description = data.get('description', record.description if record.description else '')
                    authors = data.get('authors', [])
                    if authors:
                        author_keys = [a.get('key') for a in authors if 'key' in a]
                        if author_keys:
                            author_url = f"https://openlibrary.org{author_keys[0]}.json"
                            author_response = requests.get(author_url, timeout=10)
                            if author_response.status_code == 200:
                                author_data = author_response.json()
                                autor_nombre = author_data.get('name')
                                autor_obj = self.env['biblioteca.autor'].search([('firstname', '=', autor_nombre)], limit=1)
                                if not autor_obj and autor_nombre:
                                    autor_obj = self.env['biblioteca.autor'].create({'firstname': autor_nombre})
                                record.autor = autor_obj.id
                else:
                    raise ValidationError(_("No se encontró información para el ISBN ingresado."))
            except Exception as e:
                raise ValidationError(_("Error al conectar con Open Library: %s") % str(e))


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
