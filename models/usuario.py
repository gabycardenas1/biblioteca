# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

# =============================
# MODELO: USUARIO
# =============================
class BibliotecaUsuario(models.Model):
    _name = 'biblioteca.usuarios'
    _description = 'Usuarios de la biblioteca'
    _rec_name = 'nombre_completo'

    nombre_completo = fields.Char(
        string='Nombre completo',
        required=True
    )

    cedula = fields.Char(
        string='Cédula o ID',
        required=True
    )

    correo = fields.Char(
        string='Correo electrónico'
    )

    telefono = fields.Char(
        string='Teléfono'
    )

    direccion = fields.Char(
        string='Dirección'
    )

    fecha_registro = fields.Datetime(
        string='Fecha de registro',
        default=fields.Datetime.now
    )

    prestamo_ids = fields.One2many(
        'biblioteca.prestamo',
        'usuario_id',
        string='Préstamos realizados'
    )

    multa_ids = fields.One2many(
        'biblioteca.multa',
        'usuario_id',
        string='Multas registradas'
    )

    # -----------------------------
    # VALIDACIÓN DE CÉDULA
    # -----------------------------
    @api.constrains('cedula')
    def _check_cedula(self):
        for record in self:
            if record.cedula and not record.validar_cedula_ecuador(record.cedula):
                raise ValidationError(_("La cédula ingresada no es válida."))

    def validar_cedula_ecuador(self, cedula):
        """Valida cédula ecuatoriana de 10 dígitos."""
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
