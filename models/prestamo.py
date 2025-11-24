# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class BibliotecaPrestamo(models.Model):
    _name = 'biblioteca.prestamo'
    _description = 'Registro de préstamos de la biblioteca'
    _rec_name = 'name'

    name = fields.Char(
        string='Referencia del préstamo',
        default=lambda self: _('Préstamo - %s') % fields.Date.today()
    )

    fecha_prestamo = fields.Datetime(string='Fecha de préstamo')
    fecha_max_devolucion = fields.Datetime(string='Fecha máxima de devolución', readonly=True)
    fecha_devolucion = fields.Datetime(string='Fecha de devolución')

    libro_ids = fields.Many2many(
        'biblioteca.libro',
        'prestamo_libro_rel',
        'prestamo_id',
        'libro_id',
        string='Libros'
    )

    usuario_id = fields.Many2one('biblioteca.usuarios', string='Usuario', required=True)
    personal_id = fields.Many2one('biblioteca.personal', string='Personal que presta', required=True)

    estado = fields.Selection([
        ('borrador', 'Borrador'),
        ('prestado', 'Prestado'),
        ('devuelto', 'Devuelto'),
        ('multa', 'Multa')
    ], string='Estado', default='borrador')

    multa_ids = fields.One2many('biblioteca.multa', 'prestamo_id', string='Multas')
    tiene_multa = fields.Boolean(string='¿Tiene multa?', compute="_compute_tiene_multa", store=True)
    multa_total = fields.Float(string='Total multa', compute="_compute_multa_total", store=True)


    @api.depends('multa_ids')
    def _compute_tiene_multa(self):
        for record in self:
            record.tiene_multa = bool(record.multa_ids)

    @api.depends('multa_ids.valor')
    def _compute_multa_total(self):
        for record in self:
            record.multa_total = sum(record.multa_ids.mapped('valor'))

  
    @api.onchange('fecha_prestamo')
    def _onchange_fecha_prestamo(self):
        for r in self:
            if r.fecha_prestamo:
                r.fecha_max_devolucion = r.fecha_prestamo + timedelta(days=15)

    def action_prestar(self):
        for record in self:
            if not record.usuario_id or not record.personal_id or not record.libro_ids:
                raise ValidationError("Debe asignar un usuario, un personal y al menos un libro.")

            # Validar inventario disponible
            for libro in record.libro_ids:
                if libro.ejemplares_disponibles <= 0:
                    raise ValidationError(
                        _("No hay ejemplares disponibles del libro: %s") % (libro.name)
                    )

            # Descontar inventario
            for libro in record.libro_ids:
                libro.ejemplares -= 1

            # Si la fecha no fue seleccionada, se usa la actual
            if not record.fecha_prestamo:
                record.fecha_prestamo = datetime.now()

            record.fecha_max_devolucion = record.fecha_prestamo + timedelta(days=15)
            record.estado = 'prestado'

    def action_devolver(self):
        for record in self:

            # Devolver inventario
            for libro in record.libro_ids:
                libro.ejemplares += 1

            record.fecha_devolucion = datetime.now()

            # Crear multa automática si corresponde
            record._generar_multa_retraso()

            # Estado final
            if record.tiene_multa:
                record.estado = 'multa'
            else:
                record.estado = 'devuelto'

 
    def _generar_multa_retraso(self):
        for record in self:

            if not record.fecha_max_devolucion:
                return

            fecha_ref = record.fecha_devolucion or fields.Datetime.now()
            retraso_dias = (fecha_ref - record.fecha_max_devolucion).days

            if retraso_dias <= 0:
                return

            # Crear multa por retraso
            self.env['biblioteca.multa'].create({
                'usuario_id': record.usuario_id.id,
                'prestamo_id': record.id,
                'tipo': 'retraso',
                'descripcion': 'Multa automática por retraso (%s días)' % retraso_dias,
            })
