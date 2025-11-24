# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class BibliotecaMulta(models.Model):
    _name = 'biblioteca.multa'
    _description = 'Registro de multas de la biblioteca'

    TIPO_MULTA = [
        ('retraso', 'Por retraso'),
        ('danio', 'Por daño'),
        ('perdida', 'Por pérdida'),
        ('no_devolucion', 'No devolución'),
    ]

    usuario_id = fields.Many2one('biblioteca.usuarios', string='Usuario', required=True)
    prestamo_id = fields.Many2one('biblioteca.prestamo', string='Préstamo relacionado', required=True)

    tipo = fields.Selection(TIPO_MULTA, string='Tipo de multa', required=True)
    valor = fields.Float(string='Valor de la multa', compute="_compute_valor", store=True)
    fecha = fields.Datetime(string='Fecha de multa', default=fields.Datetime.now)
    descripcion = fields.Text(string='Descripción')

    @api.depends('tipo', 'prestamo_id.fecha_max_devolucion', 'prestamo_id.fecha_devolucion')
    def _compute_valor(self):
        valores_base = {
            'retraso': 5.0,    # por cada día o fijo, según tu criterio
            'danio': 10.0,
            'perdida': 20.0,
            'no_devolucion': 50.0,
        }
        for record in self:
            if record.tipo == 'retraso' and record.prestamo_id:
                fecha_lim = record.prestamo_id.fecha_max_devolucion
                fecha_real = record.prestamo_id.fecha_devolucion or fields.Datetime.now()
                if fecha_lim and fecha_real > fecha_lim:
                    dias_retraso = (fecha_real - fecha_lim).days
                    # aquí puedes usar por día, o fijo:
                    record.valor = valores_base['retraso'] * max(dias_retraso, 1)
                else:
                    record.valor = 0.0
            else:
                record.valor = valores_base.get(record.tipo, 0.0)

    @api.model
    def create(self, vals):
        recs = super().create(vals)
        for multa in recs:
            if multa.prestamo_id:
                multa.prestamo_id.estado = 'multa'
        return recs
