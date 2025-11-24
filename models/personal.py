# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class BibliotecaPersonal(models.Model):
    _name = 'biblioteca.personal'
    _description = 'Personal de la biblioteca'
    _rec_name = 'nombre_completo'

    nombre = fields.Char(
        string='Nombre',
        required=True,
        placeholder='Ingrese el nombre del personal'
    )

    apellido = fields.Char(
        string='Apellido',
        required=True,
        placeholder='Ingrese el apellido del personal'
    )

    nombre_completo = fields.Char(
        string='Nombre completo',
        compute='_compute_nombre_completo',
        store=True
    )

    codigo = fields.Char(
        string='Código interno',
        required=True,
        placeholder='Código del personal'
    )

    cedula = fields.Char(
        string='Cédula o ID',
        required=True,
        placeholder='Ingrese número de cédula'
    )

    correo = fields.Char(
        string='Correo electrónico',
        placeholder='Ingrese correo electrónico',
        email=True
    )

    telefono = fields.Char(
        string='Teléfono',
        placeholder='Ingrese número de teléfono'
    )

    direccion = fields.Char(
        string='Dirección',
        placeholder='Ingrese dirección'
    )

    _sql_constraints = [
        ('cedula_unique', 'unique(cedula)', 'La cédula ya existe.'),
        ('codigo_unique', 'unique(codigo)', 'El código interno ya existe.')
    ]

    @api.depends('nombre', 'apellido')
    def _compute_nombre_completo(self):
        for record in self:
            record.nombre_completo = f"{record.nombre or ''} {record.apellido or ''}".strip()

    @api.constrains('cedula')
    def _check_cedula(self):
        for record in self:
            if record.cedula and not self.validar_cedula_ecuador(record.cedula):
                raise ValidationError(_("La cédula ingresada no es válida."))

    def validar_cedula_ecuador(self, cedula):
        """Valida cédula ecuatoriana estándar de 10 dígitos."""
        if not cedula or len(cedula) != 10 or not cedula.isdigit():
            return False

        provincia = int(cedula[:2])
        if provincia < 1 or provincia > 24:
            return False

        tercer_digito = int(cedula[2])
        if tercer_digito >= 6:
            return False

        coef = [2, 1, 2, 1, 2, 1, 2, 1, 2]
        total = 0
        for i in range(9):
            valor = int(cedula[i]) * coef[i]
            if valor >= 10:
                valor -= 9
            total += valor

        verificador = int(cedula[9])
        decena = ((total + 9) // 10) * 10
        return verificador == (decena - total) % 10
