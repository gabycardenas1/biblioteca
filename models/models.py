# -*- coding: utf-8 -*-

from odoo import models, fields, api

# Crea tabla biblioteca_libro
class Biblioteca(models.Model):
    _name = 'biblioteca.libro'
    _description = 'biblioteca.biblioteca'

    # Añadir las que vea necesarias
    name = fields.Char(string='Nombre libro')
    autor = fields.Many2one('biblioteca.autor', string = 'Autor del libro')
    ejemplares = fields.Integer(string='Número de ejemplares')
    costo = fields.Float(compute="_value_pc", store=True, string='Costo')
    description = fields.Text(string='Resumen del libro')
    categoria = fields.Char(string = "Categoria")
    ubicacion = fields.Char(string = 'Ubicación física')
    prestamo_id = fields.Many2one('biblioteca.prestamo', string='Préstamo asociado')
    multa_id = fields.Many2one('biblioteca.multa', string='Multa asociada')

    # Cálculo automático (Hay que mejorarlo, aún no tiene sentido)
    @api.depends('ejemplares')
    def _value_pc(self):
        for record in self:
            record.costo = (record.ejemplares or 0) * 1.5

# Crea tabla biblioteca_autor
class BibliotecaAutor(models.Model):
    _name = 'biblioteca.autor'
    _description = 'Registro de autores'
    _rec_name = 'firstname'
    
    firstname = fields.Char(string = 'Nombre')
    lastname = fields.Char(string = 'Apellido')

# Crea tabla biblioteca_prestamo
class BibliotecaPrestamo(models.Model):
    _name = 'biblioteca.prestamo'
    _description = 'Registro de préstamos de la biblioteca'
    
    name = fields.Char(string = 'Nombre')
    fecha_prestamo = fields.Datetime(string = 'Fecha de préstamo')
    libro_id = fields.One2many('biblioteca.libro', 'prestamo_id', string = 'Libro')
    usuario_id = fields.Many2one('biblioteca.usuarios', string = 'Usuarios')
    fecha_devolucion = fields.Datetime(string = 'Fecha de devolución')
    multa_bol = fields.Boolean(default = False)
    multa = fields.Float()
    
# Crea tabla biblioteca_multa
class BibliotecaMulta(models.Model):
    _name = 'biblioteca.multa'
    _description = 'Registro de multas de la biblioteca'
    _rec_name = 'name_multa'
    
    name_multa = fields.Char(string='Código de multa')
    fecha_prestamo = fields.Datetime(string='Fecha de préstamo')
    libro_id = fields.One2many('biblioteca.libro', 'multa_id', string='Libro asociado')
    usuario_id = fields.Many2one('biblioteca.usuarios', string='Usuario')
    fecha_devolucion = fields.Datetime(string='Fecha de devolución')

# Crea tabla biblioteca_usuarios
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
