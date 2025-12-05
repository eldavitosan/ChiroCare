-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Servidor: 127.0.0.1
-- Tiempo de generación: 03-12-2025 a las 23:53:27
-- Versión del servidor: 10.4.32-MariaDB
-- Versión de PHP: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Base de datos: `chiropractic`
--

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `anamnesis`
--

CREATE TABLE `anamnesis` (
  `id_anamnesis` int(11) NOT NULL,
  `id_px` int(11) NOT NULL,
  `fecha` date NOT NULL,
  `condicion1` varchar(50) DEFAULT NULL,
  `calif1` int(2) DEFAULT NULL,
  `condicion2` varchar(50) DEFAULT NULL,
  `calif2` int(2) DEFAULT NULL,
  `condicion3` varchar(50) DEFAULT NULL,
  `calif3` int(2) DEFAULT NULL,
  `como_comenzo` int(1) DEFAULT NULL,
  `primera_vez` varchar(30) DEFAULT NULL,
  `alivia` varchar(50) DEFAULT NULL,
  `empeora` varchar(50) DEFAULT NULL,
  `como_ocurrio` varchar(50) DEFAULT NULL,
  `actividades_afectadas` varchar(50) DEFAULT NULL,
  `dolor_intenso` varchar(50) DEFAULT NULL,
  `tipo_dolor` varchar(100) DEFAULT NULL,
  `lesion` varchar(50) DEFAULT NULL,
  `diagrama` varchar(500) DEFAULT NULL,
  `historia` text DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `antecedentes`
--

CREATE TABLE `antecedentes` (
  `id_antecedente` int(11) NOT NULL,
  `id_px` int(11) NOT NULL,
  `fecha` date NOT NULL,
  `peso` int(11) DEFAULT NULL,
  `altura` varchar(11) DEFAULT NULL,
  `calzado` decimal(10,1) DEFAULT NULL,
  `condiciones_generales` text DEFAULT NULL,
  `condicion_diagnosticada` text DEFAULT NULL,
  `presion_alta` varchar(20) DEFAULT NULL,
  `trigliceridos` varchar(20) DEFAULT NULL,
  `diabetes` varchar(20) DEFAULT NULL,
  `agua` varchar(20) DEFAULT NULL,
  `notas` text DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `centro`
--

CREATE TABLE `centro` (
  `id_centro` int(11) NOT NULL,
  `nombre` varchar(60) NOT NULL,
  `direccion` varchar(500) DEFAULT NULL,
  `cel` bigint(11) DEFAULT NULL,
  `tel` bigint(11) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `datos_personales`
--

CREATE TABLE `datos_personales` (
  `id_px` int(11) NOT NULL,
  `id_dr` int(5) DEFAULT NULL COMMENT 'FK a dr (Quien registró)',
  `fecha` date DEFAULT NULL,
  `comoentero` varchar(25) DEFAULT NULL,
  `nombre` varchar(40) NOT NULL,
  `apellidop` varchar(20) NOT NULL,
  `apellidom` varchar(20) DEFAULT NULL,
  `nacimiento` varchar(11) DEFAULT NULL,
  `direccion` varchar(200) DEFAULT NULL,
  `municipio` varchar(15) DEFAULT NULL,
  `estado` varchar(10) DEFAULT NULL,
  `cp` int(11) DEFAULT NULL,
  `estadocivil` varchar(15) DEFAULT NULL,
  `hijos` varchar(20) DEFAULT NULL,
  `ocupacion` varchar(20) DEFAULT NULL,
  `telcasa` bigint(11) DEFAULT NULL,
  `cel` bigint(11) DEFAULT NULL,
  `correo` varchar(45) DEFAULT NULL,
  `emergencia` bigint(11) DEFAULT NULL,
  `contacto` varchar(40) DEFAULT NULL,
  `parentesco` varchar(20) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `dr`
--

CREATE TABLE `dr` (
  `id_dr` int(11) NOT NULL,
  `nombre` varchar(45) DEFAULT NULL,
  `contraseña` varchar(255) NOT NULL,
  `usuario` varchar(50) NOT NULL,
  `centro` int(11) DEFAULT NULL,
  `esta_activo` tinyint(1) NOT NULL DEFAULT 1 COMMENT '1 si el doctor está activo, 0 si está deshabilitado',
  `config_redireccion_seguimiento` int(11) DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `notas_generales`
--

CREATE TABLE `notas_generales` (
  `id_nota` int(11) NOT NULL,
  `id_px` int(11) NOT NULL,
  `fecha` date NOT NULL,
  `notas` varchar(500) NOT NULL,
  `visto` tinyint(1) DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `plancuidado`
--

CREATE TABLE `plancuidado` (
  `id_plan` int(11) NOT NULL,
  `id_px` int(11) NOT NULL,
  `id_dr` int(11) DEFAULT NULL COMMENT 'FK a dr (Quien creó el plan)',
  `fecha` date NOT NULL,
  `pb_diagnostico` varchar(255) DEFAULT NULL,
  `plan_descripcion` text DEFAULT NULL COMMENT 'Descripción general del plan (obsoleto?)',
  `visitas_qp` int(11) DEFAULT 0 COMMENT 'Número sesiones Quiropráctica',
  `visitas_tf` int(11) DEFAULT 0 COMMENT 'Número sesiones Terapia Física',
  `etapa` varchar(30) DEFAULT NULL COMMENT 'Texto: Sintomatico, Correctivo, Mantenimiento, etc.',
  `inversion_total` decimal(10,2) DEFAULT 0.00 COMMENT 'Costo calculado',
  `promocion_pct` int(11) DEFAULT 0 COMMENT 'Porcentaje descuento',
  `ahorro_calculado` decimal(10,2) DEFAULT 0.00,
  `adicionales_ids` text DEFAULT NULL COMMENT 'IDs prod servicios adicionales (0,id,id)',
  `notas_plan` text DEFAULT NULL,
  `fecha_registro` timestamp NOT NULL DEFAULT current_timestamp() COMMENT 'Timestamp de cuando se guardó'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `postura`
--

CREATE TABLE `postura` (
  `id_postura` int(11) NOT NULL,
  `id_px` int(11) NOT NULL,
  `fecha` date NOT NULL,
  `notas_pruebas_ortoneuro` text DEFAULT NULL COMMENT 'Notas de pruebas ortopédicas y neurológicas',
  `frente` varchar(255) DEFAULT NULL COMMENT 'Ruta archivo foto frente',
  `lado` varchar(255) DEFAULT NULL COMMENT 'Ruta archivo foto lado',
  `postura_extra` varchar(255) DEFAULT NULL COMMENT 'Ruta archivo 3ra foto postura',
  `pies` varchar(255) DEFAULT NULL COMMENT 'Ruta archivo examen pisada',
  `pies_frontal` varchar(255) DEFAULT NULL COMMENT 'Ruta archivo foto frontal pisada',
  `pies_trasera` varchar(255) DEFAULT NULL COMMENT 'Ruta archivo foto trasera pisada',
  `pie_cm` decimal(11,1) DEFAULT NULL,
  `zapato_cm` decimal(11,1) DEFAULT NULL,
  `tipo_calzado` varchar(25) DEFAULT NULL,
  `termografia` varchar(255) DEFAULT NULL COMMENT 'Ruta archivo escaner espalda',
  `fuerza_izq` decimal(5,2) DEFAULT NULL,
  `fuerza_der` decimal(5,2) DEFAULT NULL,
  `oxigeno` int(3) DEFAULT NULL,
  `notas_plantillas` text DEFAULT NULL COMMENT 'Notas específicas sobre plantillas u ortesis',
  `rx` text DEFAULT NULL COMMENT 'Columna original (ahora obsoleta, usar tabla radiografias)'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `productos_servicios`
--

CREATE TABLE `productos_servicios` (
  `id_prod` int(11) NOT NULL,
  `nombre` varchar(50) NOT NULL,
  `costo` decimal(10,2) DEFAULT 0.00,
  `venta` decimal(10,2) DEFAULT 0.00,
  `adicional` tinyint(1) NOT NULL COMMENT '0=Base (QP/TF), 1=Adicional Plan, 2=Terapia Física Seguimiento',
  `esta_activo` tinyint(1) NOT NULL DEFAULT 1 COMMENT '1 si está activo y disponible para venta, 0 si está deshabilitado/oculto'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `quiropractico`
--

CREATE TABLE `quiropractico` (
  `id_seguimiento` int(11) NOT NULL,
  `id_px` int(11) NOT NULL,
  `id_dr` int(11) DEFAULT NULL COMMENT 'FK al doctor que realizó el seguimiento',
  `fecha` date NOT NULL,
  `occipital` varchar(100) DEFAULT NULL,
  `atlas` varchar(100) DEFAULT NULL,
  `axis` varchar(100) DEFAULT NULL,
  `c3` varchar(100) DEFAULT NULL,
  `c4` varchar(100) DEFAULT NULL,
  `c5` varchar(100) DEFAULT NULL,
  `c6` varchar(100) DEFAULT NULL,
  `c7` varchar(100) DEFAULT NULL,
  `t1` varchar(100) DEFAULT NULL,
  `t2` varchar(100) DEFAULT NULL,
  `t3` varchar(100) DEFAULT NULL,
  `t4` varchar(100) DEFAULT NULL,
  `t5` varchar(100) DEFAULT NULL,
  `t6` varchar(100) DEFAULT NULL,
  `t7` varchar(100) DEFAULT NULL,
  `t8` varchar(100) DEFAULT NULL,
  `t9` varchar(100) DEFAULT NULL,
  `t10` varchar(100) DEFAULT NULL,
  `t11` varchar(100) DEFAULT NULL,
  `t12` varchar(100) DEFAULT NULL,
  `l1` varchar(100) DEFAULT NULL,
  `l2` varchar(100) DEFAULT NULL,
  `l3` varchar(100) DEFAULT NULL,
  `l4` varchar(100) DEFAULT NULL,
  `l5` varchar(100) DEFAULT NULL,
  `sacro` varchar(100) DEFAULT NULL,
  `coxis` varchar(100) DEFAULT NULL,
  `iliaco_d` varchar(100) DEFAULT NULL,
  `iliaco_i` varchar(100) DEFAULT NULL,
  `notas` text DEFAULT NULL,
  `terapia` varchar(100) DEFAULT NULL,
  `pubis` varchar(100) DEFAULT NULL,
  `id_plan_cuidado_asociado` int(11) DEFAULT NULL COMMENT 'FK al plan de cuidado asociado'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `radiografias`
--

CREATE TABLE `radiografias` (
  `id_radiografia` int(11) NOT NULL,
  `id_postura` int(11) NOT NULL COMMENT 'Clave foránea a la tabla postura',
  `fecha_carga` timestamp NOT NULL DEFAULT current_timestamp(),
  `ruta_archivo` varchar(255) NOT NULL COMMENT 'Ruta relativa al archivo de imagen'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='Almacena rutas a radiografías asociadas a un registro de postura.';

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `recibos`
--

CREATE TABLE `recibos` (
  `id_recibo` int(11) NOT NULL,
  `id_px` int(11) NOT NULL COMMENT 'FK a datos_personales',
  `id_dr` int(11) DEFAULT NULL COMMENT 'FK a dr (Quien generó el recibo)',
  `fecha` date NOT NULL COMMENT 'Fecha de emisión',
  `subtotal_bruto` decimal(10,2) DEFAULT 0.00 COMMENT 'Suma de (cantidad * costo_unitario) de detalles',
  `descuento_total` decimal(10,2) DEFAULT 0.00 COMMENT 'Descuento aplicado al total',
  `total_neto` decimal(10,2) DEFAULT 0.00 COMMENT 'subtotal_bruto - descuento_total',
  `pago_efectivo` decimal(10,2) DEFAULT 0.00 COMMENT 'Monto pagado en efectivo',
  `pago_tarjeta` decimal(10,2) DEFAULT 0.00 COMMENT 'Monto pagado con tarjeta',
  `pago_transferencia` decimal(10,2) DEFAULT 0.00 COMMENT 'Monto pagado por transferencia',
  `pago_otro` decimal(10,2) DEFAULT 0.00 COMMENT 'Monto pagado por otro método',
  `pago_otro_desc` varchar(50) DEFAULT NULL COMMENT 'Descripción del otro método',
  `cambio` decimal(10,2) DEFAULT 0.00 COMMENT 'Calculado: monto_pagado - total_neto',
  `notas` text DEFAULT NULL COMMENT 'Notas generales del recibo',
  `fecha_registro` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='Información principal de cada recibo de pago.';

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `recibo_detalle`
--

CREATE TABLE `recibo_detalle` (
  `id_detalle` int(11) NOT NULL,
  `id_recibo` int(11) NOT NULL COMMENT 'FK a recibos',
  `id_prod` int(11) NOT NULL COMMENT 'FK a productos_servicios',
  `cantidad` int(11) NOT NULL DEFAULT 1,
  `descripcion_prod` varchar(100) DEFAULT NULL COMMENT 'Nombre del producto/servicio al momento de la venta (opcional, por si cambia)',
  `costo_unitario_compra` decimal(10,2) DEFAULT 0.00 COMMENT 'Costo unitario del producto/servicio para la clínica al momento de la venta',
  `costo_unitario_venta` decimal(10,2) NOT NULL COMMENT 'Precio de venta unitario al momento de la transacción',
  `descuento_linea` decimal(10,2) DEFAULT 0.00 COMMENT 'Descuento específico para esta línea (opcional)',
  `subtotal_linea_neto` decimal(10,2) NOT NULL COMMENT 'Calculado: (cantidad * costo_unitario_venta) - descuento_linea'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='Líneas de detalle para cada recibo.';

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `revaloraciones`
--

CREATE TABLE `revaloraciones` (
  `id_revaloracion` int(11) NOT NULL,
  `id_px` int(11) NOT NULL COMMENT 'FK a datos_personales',
  `id_dr` int(11) NOT NULL COMMENT 'FK a dr (quien hizo la revaloración)',
  `fecha` date NOT NULL COMMENT 'Fecha de la revaloración',
  `id_anamnesis_inicial` int(11) DEFAULT NULL COMMENT 'FK Opcional a anamnesis (para vincular al motivo inicial)',
  `id_postura_asociado` int(11) DEFAULT NULL,
  `calif1_actual` int(2) DEFAULT NULL COMMENT 'Severidad actual condición 1',
  `calif2_actual` int(2) DEFAULT NULL COMMENT 'Severidad actual condición 2',
  `calif3_actual` int(2) DEFAULT NULL COMMENT 'Severidad actual condición 3',
  `mejora_subjetiva_pct` int(3) DEFAULT NULL COMMENT 'Porcentaje de mejora percibido por el paciente (0-100)',
  `diagrama_actual` varchar(500) DEFAULT NULL COMMENT 'IDs de zonas de dolor actuales',
  `notas_adicionales_reval` text DEFAULT NULL COMMENT 'Notas adicionales o cualitativas de la revaloración',
  `fecha_registro` timestamp NOT NULL DEFAULT current_timestamp() COMMENT 'Timestamp de cuando se guardó'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='Registros de hitos de revaloración del paciente.';

--
-- Índices para tablas volcadas
--

--
-- Indices de la tabla `anamnesis`
--
ALTER TABLE `anamnesis`
  ADD PRIMARY KEY (`id_anamnesis`),
  ADD UNIQUE KEY `uq_anamnesis_paciente_fecha` (`id_px`,`fecha`),
  ADD KEY `idx_anamnesis_paciente_fecha` (`id_px`,`fecha`);

--
-- Indices de la tabla `antecedentes`
--
ALTER TABLE `antecedentes`
  ADD PRIMARY KEY (`id_antecedente`),
  ADD KEY `idx_antecedentes_paciente_fecha` (`id_px`,`fecha`);

--
-- Indices de la tabla `centro`
--
ALTER TABLE `centro`
  ADD PRIMARY KEY (`id_centro`);

--
-- Indices de la tabla `datos_personales`
--
ALTER TABLE `datos_personales`
  ADD PRIMARY KEY (`id_px`),
  ADD KEY `fk_datos_personales_doctor_idx` (`id_dr`);

--
-- Indices de la tabla `dr`
--
ALTER TABLE `dr`
  ADD PRIMARY KEY (`id_dr`),
  ADD UNIQUE KEY `usuario_UNIQUE` (`usuario`);

--
-- Indices de la tabla `notas_generales`
--
ALTER TABLE `notas_generales`
  ADD PRIMARY KEY (`id_nota`),
  ADD KEY `fk_notas_paciente_idx` (`id_px`);

--
-- Indices de la tabla `plancuidado`
--
ALTER TABLE `plancuidado`
  ADD PRIMARY KEY (`id_plan`),
  ADD KEY `idx_plancuidado_paciente_fecha` (`id_px`,`fecha`),
  ADD KEY `fk_plancuidado_doctor_idx` (`id_dr`);

--
-- Indices de la tabla `postura`
--
ALTER TABLE `postura`
  ADD PRIMARY KEY (`id_postura`),
  ADD KEY `idx_postura_paciente_fecha` (`id_px`,`fecha`);

--
-- Indices de la tabla `productos_servicios`
--
ALTER TABLE `productos_servicios`
  ADD PRIMARY KEY (`id_prod`);

--
-- Indices de la tabla `quiropractico`
--
ALTER TABLE `quiropractico`
  ADD PRIMARY KEY (`id_seguimiento`),
  ADD KEY `idx_quiropractico_paciente_fecha` (`id_px`,`fecha`),
  ADD KEY `fk_seguimiento_plan_cuidado` (`id_plan_cuidado_asociado`),
  ADD KEY `fk_quiropractico_doctor` (`id_dr`);

--
-- Indices de la tabla `radiografias`
--
ALTER TABLE `radiografias`
  ADD PRIMARY KEY (`id_radiografia`),
  ADD KEY `fk_radiografias_postura_idx` (`id_postura`);

--
-- Indices de la tabla `recibos`
--
ALTER TABLE `recibos`
  ADD PRIMARY KEY (`id_recibo`),
  ADD KEY `idx_recibos_paciente_fecha` (`id_px`,`fecha`),
  ADD KEY `fk_recibos_doctor_idx` (`id_dr`);

--
-- Indices de la tabla `recibo_detalle`
--
ALTER TABLE `recibo_detalle`
  ADD PRIMARY KEY (`id_detalle`),
  ADD KEY `fk_recibo_detalle_recibo_idx` (`id_recibo`),
  ADD KEY `fk_recibo_detalle_producto_idx` (`id_prod`);

--
-- Indices de la tabla `revaloraciones`
--
ALTER TABLE `revaloraciones`
  ADD PRIMARY KEY (`id_revaloracion`),
  ADD KEY `idx_revaloracion_paciente_fecha` (`id_px`,`fecha`),
  ADD KEY `fk_revaloracion_paciente_idx` (`id_px`),
  ADD KEY `fk_revaloracion_doctor_idx` (`id_dr`),
  ADD KEY `fk_revaloracion_anamnesis_idx` (`id_anamnesis_inicial`),
  ADD KEY `fk_revaloracion_postura` (`id_postura_asociado`);

--
-- AUTO_INCREMENT de las tablas volcadas
--

--
-- AUTO_INCREMENT de la tabla `anamnesis`
--
ALTER TABLE `anamnesis`
  MODIFY `id_anamnesis` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `antecedentes`
--
ALTER TABLE `antecedentes`
  MODIFY `id_antecedente` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `centro`
--
ALTER TABLE `centro`
  MODIFY `id_centro` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `datos_personales`
--
ALTER TABLE `datos_personales`
  MODIFY `id_px` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `dr`
--
ALTER TABLE `dr`
  MODIFY `id_dr` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `notas_generales`
--
ALTER TABLE `notas_generales`
  MODIFY `id_nota` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `plancuidado`
--
ALTER TABLE `plancuidado`
  MODIFY `id_plan` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `postura`
--
ALTER TABLE `postura`
  MODIFY `id_postura` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `productos_servicios`
--
ALTER TABLE `productos_servicios`
  MODIFY `id_prod` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `quiropractico`
--
ALTER TABLE `quiropractico`
  MODIFY `id_seguimiento` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `radiografias`
--
ALTER TABLE `radiografias`
  MODIFY `id_radiografia` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `recibos`
--
ALTER TABLE `recibos`
  MODIFY `id_recibo` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `recibo_detalle`
--
ALTER TABLE `recibo_detalle`
  MODIFY `id_detalle` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `revaloraciones`
--
ALTER TABLE `revaloraciones`
  MODIFY `id_revaloracion` int(11) NOT NULL AUTO_INCREMENT;

--
-- Restricciones para tablas volcadas
--

--
-- Filtros para la tabla `anamnesis`
--
ALTER TABLE `anamnesis`
  ADD CONSTRAINT `fk_anamnesis_paciente` FOREIGN KEY (`id_px`) REFERENCES `datos_personales` (`id_px`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Filtros para la tabla `antecedentes`
--
ALTER TABLE `antecedentes`
  ADD CONSTRAINT `fk_antecedentes_paciente` FOREIGN KEY (`id_px`) REFERENCES `datos_personales` (`id_px`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Filtros para la tabla `datos_personales`
--
ALTER TABLE `datos_personales`
  ADD CONSTRAINT `fk_datos_personales_doctor` FOREIGN KEY (`id_dr`) REFERENCES `dr` (`id_dr`) ON DELETE SET NULL ON UPDATE CASCADE;

--
-- Filtros para la tabla `notas_generales`
--
ALTER TABLE `notas_generales`
  ADD CONSTRAINT `fk_notas_paciente` FOREIGN KEY (`id_px`) REFERENCES `datos_personales` (`id_px`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Filtros para la tabla `plancuidado`
--
ALTER TABLE `plancuidado`
  ADD CONSTRAINT `fk_plancuidado_doctor` FOREIGN KEY (`id_dr`) REFERENCES `dr` (`id_dr`) ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_plancuidado_paciente` FOREIGN KEY (`id_px`) REFERENCES `datos_personales` (`id_px`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Filtros para la tabla `postura`
--
ALTER TABLE `postura`
  ADD CONSTRAINT `fk_postura_paciente` FOREIGN KEY (`id_px`) REFERENCES `datos_personales` (`id_px`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Filtros para la tabla `quiropractico`
--
ALTER TABLE `quiropractico`
  ADD CONSTRAINT `fk_quiropractico_doctor` FOREIGN KEY (`id_dr`) REFERENCES `dr` (`id_dr`) ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_quiropractico_paciente` FOREIGN KEY (`id_px`) REFERENCES `datos_personales` (`id_px`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_seguimiento_plan_cuidado` FOREIGN KEY (`id_plan_cuidado_asociado`) REFERENCES `plancuidado` (`id_plan`) ON DELETE SET NULL ON UPDATE CASCADE;

--
-- Filtros para la tabla `radiografias`
--
ALTER TABLE `radiografias`
  ADD CONSTRAINT `fk_radiografias_postura` FOREIGN KEY (`id_postura`) REFERENCES `postura` (`id_postura`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Filtros para la tabla `recibos`
--
ALTER TABLE `recibos`
  ADD CONSTRAINT `fk_recibos_doctor` FOREIGN KEY (`id_dr`) REFERENCES `dr` (`id_dr`) ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_recibos_paciente` FOREIGN KEY (`id_px`) REFERENCES `datos_personales` (`id_px`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Filtros para la tabla `recibo_detalle`
--
ALTER TABLE `recibo_detalle`
  ADD CONSTRAINT `fk_recibo_detalle_producto` FOREIGN KEY (`id_prod`) REFERENCES `productos_servicios` (`id_prod`) ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_recibo_detalle_recibo` FOREIGN KEY (`id_recibo`) REFERENCES `recibos` (`id_recibo`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Filtros para la tabla `revaloraciones`
--
ALTER TABLE `revaloraciones`
  ADD CONSTRAINT `fk_revaloracion_anamnesis` FOREIGN KEY (`id_anamnesis_inicial`) REFERENCES `anamnesis` (`id_anamnesis`) ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_revaloracion_doctor` FOREIGN KEY (`id_dr`) REFERENCES `dr` (`id_dr`) ON DELETE NO ACTION ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_revaloracion_paciente` FOREIGN KEY (`id_px`) REFERENCES `datos_personales` (`id_px`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_revaloracion_postura` FOREIGN KEY (`id_postura_asociado`) REFERENCES `postura` (`id_postura`) ON DELETE SET NULL ON UPDATE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
