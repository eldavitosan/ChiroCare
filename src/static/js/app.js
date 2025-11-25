// --- Funciones Utilitarias ---

/**
 * Calcula la edad basada en una fecha de nacimiento en formato YYYY-MM-DD.
 * @param {string} fechaNacimiento - La fecha de nacimiento (YYYY-MM-DD).
 * @returns {number|string} La edad calculada o una cadena vacía si la fecha es inválida.
 */
function calcularEdad(fechaNacimiento) {
    if (!fechaNacimiento) return '';
    try {
        const hoy = new Date();
        // Asegurarse que el formato sea consistente (YYYY-MM-DD)
        const nacimientoParts = fechaNacimiento.split('-');
        if (nacimientoParts.length !== 3) throw new Error("Formato de fecha incorrecto");
        const nacimiento = new Date(parseInt(nacimientoParts[0]), parseInt(nacimientoParts[1]) - 1, parseInt(nacimientoParts[2]));

        if (isNaN(nacimiento.getTime())) throw new Error("Fecha inválida");

        let edad = hoy.getFullYear() - nacimiento.getFullYear();
        const mes = hoy.getMonth() - nacimiento.getMonth();
        if (mes < 0 || (mes === 0 && hoy.getDate() < nacimiento.getDate())) {
            edad--;
        }
        if (isNaN(edad) || edad < 0) { return ''; }
        return edad;
    } catch (e) {
        console.error("Error parsing date in calcularEdad:", e);
        return '';
    }
}

/**
 * Inicializa un dropdown de selección de fecha para recargar la página.
 * @param {string} selectElementId - El ID del elemento <select>.
 * @param {string} baseUrl - La URL base para la recarga (sin parámetros de query).
 * @param {string} paramName - El nombre del parámetro a usar en la URL ('selected_id' o 'fecha').
 * @param {string} [todayValue=''] - El valor que representa la opción "Hoy" o "Nuevo".
 */
function initializeDateDropdown(selectElementId, baseUrl, paramName = 'selected_id', todayValue = '') {
    const dateSelect = document.getElementById(selectElementId);
    if (dateSelect) {
        dateSelect.addEventListener('change', function() {
            const selectedValue = this.value;
            const url = new URL(baseUrl, window.location.origin);

            // Limpiar parámetro existente antes de añadir el nuevo
            url.searchParams.delete('selected_id');
            url.searchParams.delete('fecha');

            if (selectedValue && selectedValue !== todayValue) {
                url.searchParams.set(paramName, selectedValue);
            } else if (selectedValue === todayValue && todayValue === 'hoy') {
                // Caso especial para /pruebas donde 'hoy' tiene significado
                url.searchParams.set('fecha', 'hoy');
            }
            // Si es todayValue='' (nuevo), no se añade parámetro, va a la URL base.

            window.location.href = url.toString();
        });
    } else {
        console.error(`Dropdown con ID '${selectElementId}' no encontrado.`);
    }
}


/**
 * Inicializa la lógica del diagrama corporal interactivo.
 * @param {string} containerId - ID del div contenedor del diagrama.
 * @param {string} hiddenInputId - ID del input oculto que guarda los puntos.
 */
function initializeBodyDiagram(containerId, hiddenInputId) {
    const diagramContainer = document.getElementById(containerId);
    const hiddenInput = document.getElementById(hiddenInputId);

    if (!diagramContainer || !hiddenInput) {
        console.error("Elementos del diagrama no encontrados:", containerId, hiddenInputId);
        return;
    }

    const points = diagramContainer.querySelectorAll('.diagram-point');
    const isEditable = !diagramContainer.classList.contains('disabled');
    let selectedPoints = new Set();

    function updateHiddenInput() {
        const valueString = '0,' + Array.from(selectedPoints).join(',');
        hiddenInput.value = (valueString === '0,') ? '0,' : valueString;
    }

    function loadSelectedPoints() {
        selectedPoints.clear();
        const savedPointsString = hiddenInput.value || '0,';
        const savedPointsArray = savedPointsString.split(',');
        points.forEach(point => {
            const pointId = point.dataset.areaId;
            if (savedPointsArray.includes(pointId)) {
                point.classList.add('selected');
                selectedPoints.add(pointId);
            } else {
                point.classList.remove('selected');
            }
        });
    }

    if (isEditable) {
        points.forEach(point => {
            point.addEventListener('click', function() {
                const pointId = this.dataset.areaId;
                this.classList.toggle('selected');
                if (this.classList.contains('selected')) {
                    selectedPoints.add(pointId);
                } else {
                    selectedPoints.delete(pointId);
                }
                updateHiddenInput();
            });
        });
    }

    loadSelectedPoints(); // Cargar estado inicial
}

/**
 * Inicializa el cálculo de costos para el plan de cuidado.
 * @param {string} qpInputId
 * @param {string} tfInputId
 * @param {string} promoInputId
 * @param {string} inversionDisplayId
 * @param {string} ahorroDisplayId
 * @param {number} costoQP
 * @param {number} costoTF
 */
function initializeCostCalculator(qpInputId, tfInputId, promoInputId, inversionDisplayId, ahorroDisplayId, costoQP, costoTF) {
    const qpInput = document.getElementById(qpInputId);
    const tfInput = document.getElementById(tfInputId);
    const promoInput = document.getElementById(promoInputId);
    const inversionDisplay = document.getElementById(inversionDisplayId);
    const ahorroDisplay = document.getElementById(ahorroDisplayId);

    function calculateAndUpdateCosts() {
        if (!qpInput || !tfInput || !promoInput || !inversionDisplay || !ahorroDisplay) { return; }
        const qp = parseInt(qpInput.value) || 0;
        const tf = parseInt(tfInput.value) || 0;
        const promo = parseInt(promoInput.value) || 0;
        const inversionBruta = (qp * costoQP) + (tf * costoTF);
        const ahorro = (inversionBruta * promo) / 100.0;
        const inversionNeta = inversionBruta - ahorro;

        const formatCurrency = (value) => {
             // Asegura que 'value' sea un número antes de formatear
             const numericValue = Number(value);
             if (isNaN(numericValue)) { return "$ 0.00"; } // O algún valor por defecto
             return numericValue.toLocaleString('es-MX', { style: 'currency', currency: 'MXN' });
         }
        inversionDisplay.textContent = formatCurrency(inversionNeta);
        ahorroDisplay.textContent = formatCurrency(ahorro);
    }

    if (qpInput) qpInput.addEventListener('input', calculateAndUpdateCosts);
    if (tfInput) tfInput.addEventListener('input', calculateAndUpdateCosts);
    if (promoInput) promoInput.addEventListener('input', calculateAndUpdateCosts);

    calculateAndUpdateCosts(); // Calcular al cargar
}

/**
 * Inicializa la funcionalidad de búsqueda y selección de pacientes en el dashboard.
 * @param {string} searchInputId
 * @param {string} searchButtonId
 * @param {string} resultsDivId
 * @param {string} resultsContainerId
 * @param {string} activePatientDisplayId
 * @param {string} clearButtonId
 * @param {string} resultsLabelId
 */
function initializePatientSearch(searchInputId, searchButtonId, resultsDivId, resultsContainerId, activePatientDisplayId, clearButtonId, resultsLabelId) {
    const searchInput = document.getElementById(searchInputId);
    const searchButton = document.getElementById(searchButtonId);
    const resultsDiv = document.getElementById(resultsDivId);
    const searchResultsContainer = document.getElementById(resultsContainerId);
    const activePatientDisplay = document.getElementById(activePatientDisplayId);
    const clearSelectionButton = document.getElementById(clearButtonId);
    const resultsLabel = document.getElementById(resultsLabelId); // Obtener el label

    if (!searchInput || !searchButton || !resultsDiv || !searchResultsContainer || !activePatientDisplay || !clearSelectionButton || !resultsLabel) {
        console.error("Error: Uno o más elementos para la búsqueda de pacientes no fueron encontrados.");
        return;
    }

    let currentSelectedPatientId = null;
    let highlightedElement = null;
    const initialResultsHTML = resultsDiv.innerHTML; // Guardar contenido inicial

    function highlightPatientRow(rowElement) {
        if (highlightedElement) { highlightedElement.classList.remove('highlighted'); }
        if (rowElement) {
            rowElement.classList.add('highlighted');
            highlightedElement = rowElement;
            // Mostrar info del paciente seleccionado en la parte superior
            currentSelectedPatientId = rowElement.dataset.patientId;
            const patientName = rowElement.dataset.patientName;
            activePatientDisplay.innerHTML = `<h3>Paciente Activo: ${patientName || 'Desconocido'}</h3>`;
            if(clearSelectionButton) {
                activePatientDisplay.appendChild(clearSelectionButton); // Mover el botón aquí
                clearSelectionButton.classList.remove('hidden'); // Mostrar el botón
            }

        } else {
            highlightedElement = null;
             currentSelectedPatientId = null;
             activePatientDisplay.innerHTML = '';
             if(clearSelectionButton) {
                 activePatientDisplay.appendChild(clearSelectionButton);
                 clearSelectionButton.classList.add('hidden');
             }
        }
    }

    function clearSelection() {
        highlightPatientRow(null); // Limpiar resaltado y display superior
        searchInput.value = '';
        resultsLabel.textContent = 'Pacientes Recientes:'; // Restaurar label
        resultsDiv.innerHTML = initialResultsHTML; // Restaurar contenido inicial
        addListenersToInitialResults(); // Re-añadir listeners
    }

    function performSearch() {
        const searchTerm = searchInput.value.trim();
        resultsLabel.textContent = 'Resultados de la búsqueda:'; // Cambiar label
        resultsDiv.innerHTML = '<div class="text-center text-muted p-3"><div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Loading...</span></div> Buscando...</div>';
        highlightPatientRow(null); // Limpiar selección previa

        if (searchTerm.length < 1) {
            clearSelection(); // Usar clearSelection para restaurar todo si la búsqueda está vacía
            return;
        }

        fetch(`/api/search_patients?term=${encodeURIComponent(searchTerm)}`)
            .then(response => response.ok ? response.json() : Promise.reject(`Error HTTP: ${response.status}`))
            .then(data => {
                resultsDiv.innerHTML = '';
                if (data && data.length > 0) {
                    data.forEach(patient => {
                         const patientDiv = document.createElement('div');
                         patientDiv.classList.add('list-group-item', 'list-group-item-action', 'd-flex', 'justify-content-between', 'align-items-center', 'patient-result-item'); // Asegurar todas las clases
                         patientDiv.dataset.patientId = patient.id_px;
                         const fullName = `${patient.nombre} ${patient.apellidop} ${patient.apellidom || ''}`;
                         patientDiv.dataset.patientName = fullName;

                         const nameSpan = document.createElement('span');
                         // Icono opcional
                         const icon = document.createElement('i');
                         icon.classList.add('fas', 'fa-user', 'me-2', 'text-secondary');
                         nameSpan.appendChild(icon);
                         nameSpan.appendChild(document.createTextNode(fullName));

                         const detailLink = document.createElement('a');
                         detailLink.href = `/paciente/detalle/${patient.id_px}`;
                         detailLink.textContent = 'Ver Detalle';
                         detailLink.classList.add('btn', 'btn-sm', 'btn-outline-primary', 'detail-link');
                         detailLink.addEventListener('click', (event) => { event.stopPropagation(); });

                         patientDiv.appendChild(nameSpan);
                         patientDiv.appendChild(detailLink);
                         resultsDiv.appendChild(patientDiv);

                         // Añadir Listener solo para resaltar al hacer click
                         addListenersToDiv(patientDiv);
                    });
                } else {
                    resultsDiv.innerHTML = '<p class="text-muted p-2">No se encontraron pacientes.</p>';
                }
            })
            .catch(error => {
                console.error('Error en la búsqueda:', error);
                resultsDiv.innerHTML = '<div class="alert alert-danger py-1 px-2">Error al buscar.</div>';
            });
    }

    function addListenersToDiv(divElement) {
         if (!divElement) return;
         divElement.addEventListener('click', function(event) {
             if (event.target.classList.contains('detail-link')) return;
             highlightPatientRow(this);
         });
     }

    function addListenersToInitialResults() {
         const initialItems = resultsDiv.querySelectorAll('.initial-patient');
         initialItems.forEach(itemDiv => {
             addListenersToDiv(itemDiv);
             const detailBtn = itemDiv.querySelector('.detail-link');
             if (detailBtn) detailBtn.addEventListener('click', (event) => { event.stopPropagation(); });
         });
     }

    // Listeners iniciales
    searchButton.addEventListener('click', performSearch);
    searchInput.addEventListener('keypress', function(event) { if (event.key === 'Enter') { event.preventDefault(); performSearch(); } });
    clearSelectionButton.addEventListener('click', clearSelection);
    addListenersToInitialResults(); // Para los pacientes recientes
}


function initializeReciboForm(isReadOnlyMode = false, initialItems = []) { // Orden de parámetros cambiado para coincidir con la llamada
    console.log("DEBUG JS: initializeReciboForm - Modo Solo Lectura:", isReadOnlyMode, "Items Iniciales:", initialItems);

    // --- Elementos del DOM (basados en tu plantilla original) ---
    const form = document.getElementById('recibo-form');
    const productSelect = document.getElementById('producto-select');
    const quantityInput = document.getElementById('producto-cantidad');
    const discountTypeSelect = document.getElementById('producto-descuento-tipo');
    const discountInput = document.getElementById('producto-descuento');
    const productPriceDisplay = document.getElementById('producto-precio-display'); // Span para precio unit.
    const lineSubtotalDisplay = document.getElementById('linea-subtotal-display'); // Span para subtotal de línea
    const addItemBtn = document.getElementById('add-item-btn');
    const detailsTableBody = document.getElementById('recibo-detalles-body');
    const subtotalBrutoDisplay = document.getElementById('subtotal-bruto-display');
    const descuentoTotalDisplay = document.getElementById('descuento-total-display');
    const totalNetoDisplay = document.getElementById('total-neto-display');
    const pagoEfectivoInput = document.getElementById('pago_efectivo');
    const pagoTarjetaInput = document.getElementById('pago_tarjeta');
    const pagoTransferenciaInput = document.getElementById('pago_transferencia');
    const pagoOtroInput = document.getElementById('pago_otro'); // Para el monto del "otro pago"
    // const pagoOtroDescInput = document.getElementById('pago_otro_desc'); // Ya no se usa directamente en JS aquí
    const paymentInputs = [pagoEfectivoInput, pagoTarjetaInput, pagoTransferenciaInput, pagoOtroInput];
    const totalPagadoDisplay = document.getElementById('total-pagado-display');
    const cambioDisplay = document.getElementById('cambio-display');
    const guardarReciboBtn = document.getElementById('guardar-recibo-btn');
    const noItemsMsg = document.getElementById('no-items-msg');
    const detallesJsonInput = document.getElementById('recibo_detalles_json');
    const subtotalHidden = document.getElementById('subtotal_bruto_hidden');
    const descuentoHidden = document.getElementById('descuento_total_hidden');
    const totalNetoHidden = document.getElementById('total_neto_hidden');
    const cambioHidden = document.getElementById('cambio_hidden'); // Input oculto para el cambio

    // Sección para agregar ítems (para ocultarla en modo readonly)
    const agregarItemsSection = addItemBtn ? addItemBtn.closest('.form-section') : null;
    // También podrías seleccionar el card completo si la estructura es fija:
    // const agregarItemsSection = document.querySelector('#recibo-form .card.mb-3');


    if (!form || !detailsTableBody) { // Verificaciones mínimas
        console.warn("DEBUG JS: Formulario 'recibo-form' o 'recibo-detalles-body' no encontrado. Saliendo de initializeReciboForm.");
        return; 
    }

    let reciboItems = []; 

    const formatCurrency = (value) => {
        const numericValue = Number(value);
        if (isNaN(numericValue)) { return "$ 0.00"; }
        return numericValue.toLocaleString('es-MX', { style: 'currency', currency: 'MXN', minimumFractionDigits: 2, maximumFractionDigits: 2 });
    };

    function updateLineSubtotal() {
        if (isReadOnlyMode || !productSelect || !quantityInput || !discountInput || !discountTypeSelect || !productPriceDisplay || !lineSubtotalDisplay) return;

        try {
            const selectedOption = productSelect.options[productSelect.selectedIndex];
            const productPrice = parseFloat(selectedOption.dataset.precio) || 0;
            const quantity = parseInt(quantityInput.value) || 0;
            const discountType = discountTypeSelect.value;
            const discountValue = parseFloat(discountInput.value) || 0;
            let discountAmount = 0;
            let lineSubtotalNet = 0;
            let lineSubtotalGross = 0;

            productPriceDisplay.textContent = formatCurrency(productPrice);

            if (quantity > 0 && productPrice >= 0) { // Permitir precio 0 para ítems de cortesía
                lineSubtotalGross = quantity * productPrice;
                if (discountType === '%') {
                    if (discountValue >= 0 && discountValue <= 100) {
                        discountAmount = (lineSubtotalGross * discountValue) / 100;
                    } else { discountAmount = 0; }
                } else { 
                    if (discountValue >= 0 && discountValue <= lineSubtotalGross) {
                        discountAmount = discountValue;
                    } else if (discountValue > lineSubtotalGross && lineSubtotalGross > 0) { // Solo si el subtotal es > 0
                         discountAmount = lineSubtotalGross;
                         discountInput.value = discountAmount.toFixed(2);
                    } else { discountAmount = 0; }
                }
                lineSubtotalNet = lineSubtotalGross - discountAmount;
            }
            lineSubtotalDisplay.textContent = formatCurrency(lineSubtotalNet);
        } catch (e) {
            console.error("Error en updateLineSubtotal:", e);
            if(lineSubtotalDisplay) lineSubtotalDisplay.textContent = "Error";
        }
    }
    
    function updateTotals() {
        let subtotalBruto = 0, descuentoAplicadoTotal = 0, totalNeto = 0, totalPagado = 0, cambio = 0;
        try {
            reciboItems.forEach(item => {
                subtotalBruto += item.cantidad * item.costo_unitario_venta;
                descuentoAplicadoTotal += item.descuento_linea;
            });
            totalNeto = subtotalBruto - descuentoAplicadoTotal;

            paymentInputs.forEach(input => {
                if (input) { totalPagado += parseFloat(input.value) || 0; }
            });
            
            // Asegurar que el cambio no sea negativo si totalNeto es 0 (ej. recibo de cortesía)
            if (totalNeto <= 0 && totalPagado <=0) {
                cambio = 0;
            } else if (totalNeto > 0) {
                 cambio = totalPagado - totalNeto;
            } else { // totalNeto es 0 o negativo, y totalPagado es > 0
                 cambio = totalPagado; // Si el neto es 0, todo lo pagado es cambio.
            }


            if(subtotalBrutoDisplay) subtotalBrutoDisplay.textContent = formatCurrency(subtotalBruto);
            if(descuentoTotalDisplay) descuentoTotalDisplay.textContent = `(${formatCurrency(descuentoAplicadoTotal)})`;
            if(totalNetoDisplay) totalNetoDisplay.textContent = formatCurrency(totalNeto);
            if(totalPagadoDisplay) totalPagadoDisplay.textContent = formatCurrency(totalPagado);
            if(cambioDisplay) cambioDisplay.textContent = formatCurrency(cambio >= 0 ? cambio : 0);

            if(subtotalHidden) subtotalHidden.value = subtotalBruto.toFixed(2);
            if(descuentoHidden) descuentoHidden.value = descuentoAplicadoTotal.toFixed(2);
            if(totalNetoHidden) totalNetoHidden.value = totalNeto.toFixed(2);
            if(cambioHidden) cambioHidden.value = (cambio >= 0 ? cambio : 0).toFixed(2);

            if (guardarReciboBtn) guardarReciboBtn.disabled = (reciboItems.length === 0 || isReadOnlyMode);
            if(noItemsMsg) noItemsMsg.style.display = reciboItems.length > 0 ? 'none' : '';
        } catch (e) {
            console.error("Error en updateTotals:", e);
        }
    }

    function renderItemRow(item) {
        const productIdForRow = item.id_prod;
        if (typeof productIdForRow === 'undefined' || productIdForRow === null) return;
        
        const row = document.createElement('tr');
        row.dataset.itemId = productIdForRow; // El HTML usa data-item-id

        // Usar item.descripcion_item si viene de la carga inicial (get_recibo_detalles_by_id)
        // o item.descripcion_prod si es un nuevo ítem agregado por el JS
        const descripcion = item.descripcion_item || item.descripcion_prod || 'N/A';
        
        row.innerHTML = `
            <td>${descripcion}</td>
            <td class="text-end">${parseInt(item.cantidad)}</td>
            <td class="text-end">${formatCurrency(item.costo_unitario_venta)}</td>
            <td class="text-end text-danger">${item.descuento_linea > 0 ? '(' + formatCurrency(item.descuento_linea) + ')' : '-'}</td>
            <td class="text-end">${formatCurrency(item.subtotal_linea_neto)}</td>
            ${!isReadOnlyMode ? '<td class="action-col"><button type="button" class="btn btn-danger btn-sm py-0 px-1 remove-item-btn" title="Eliminar"><i class="fas fa-times fa-xs"></i></button></td>' : '<td></td>'}
        `;

        detailsTableBody.appendChild(row);

        if (!isReadOnlyMode) {
            const removeBtn = row.querySelector('.remove-item-btn');
            if (removeBtn) {
                removeBtn.addEventListener('click', function() {
                    removeItem(productIdForRow);
                });
            }
        }
    }

    function removeItem(productId) {
        // Tu plantilla usa data-item-id, pero el JS interno podría estar usando id_prod.
        // Asegurémonos de que coincida o convertir.
        reciboItems = reciboItems.filter(item => String(item.id_prod) !== String(productId)); 
        
        const rowToRemove = detailsTableBody.querySelector(`tr[data-item-id="${productId}"]`);
        if (rowToRemove) { rowToRemove.remove(); }
        updateTotals();
    }

    // --- Lógica de Inicialización ---
    if (isReadOnlyMode) {
        if (agregarItemsSection) agregarItemsSection.style.display = 'none';
        if (guardarReciboBtn) guardarReciboBtn.style.display = 'none';
        // Los inputs de pago y notas ya se manejan con 'readonly' en la plantilla HTML.
        console.log("DEBUG JS: Formulario en modo Solo Lectura.");
    } else { // Modo Nuevo Recibo o Edición (si la implementas)
        if (productSelect) productSelect.addEventListener('change', updateLineSubtotal);
        if (quantityInput) quantityInput.addEventListener('input', updateLineSubtotal);
        if (discountTypeSelect) discountTypeSelect.addEventListener('change', updateLineSubtotal);
        if (discountInput) discountInput.addEventListener('input', updateLineSubtotal);
        
        if(addItemBtn) {
            addItemBtn.addEventListener('click', function() {
                const selectedOption = productSelect.options[productSelect.selectedIndex];
                const productId = selectedOption.value;
                const productName = selectedOption.text; // El texto del option
                const productPrice = parseFloat(selectedOption.dataset.precio) || 0;
                const quantity = parseInt(quantityInput.value) || 1;
                const discountType = discountTypeSelect.value;
                const discountValueInput = parseFloat(discountInput.value) || 0;
                let calculatedDiscountAmount = 0;
                
                if (!productId) { alert("Seleccione un producto."); return; }
                if (isNaN(quantity) || quantity <= 0) { alert("Cantidad inválida."); quantityInput.value = 1; return; }
                if (isNaN(productPrice) && productPrice < 0) { alert("Precio inválido."); return; } // Permitir precio 0
                if (isNaN(discountValueInput) || discountValueInput < 0) { alert("Descuento no puede ser negativo."); discountInput.value = 0; return; }

                const subtotalBrutoLinea = quantity * productPrice;
                if (discountType === '%') {
                    if (discountValueInput >= 0 && discountValueInput <= 100) {
                        calculatedDiscountAmount = (subtotalBrutoLinea * discountValueInput) / 100;
                    } else { alert("Porcentaje de descuento entre 0 y 100."); discountInput.value = 0; return; }
                } else {
                    if (discountValueInput >= 0 && discountValueInput <= subtotalBrutoLinea) {
                        calculatedDiscountAmount = discountValueInput;
                    } else if (discountValueInput > subtotalBrutoLinea && subtotalBrutoLinea > 0) {
                         alert(`Descuento ($${discountValueInput.toFixed(2)}) excede subtotal ($${subtotalBrutoLinea.toFixed(2)}). Aplicado máximo.`);
                         calculatedDiscountAmount = subtotalBrutoLinea;
                         discountInput.value = calculatedDiscountAmount.toFixed(2);
                    } else { calculatedDiscountAmount = 0;}
                }
                const subtotalNetoLinea = subtotalBrutoLinea - calculatedDiscountAmount;

                const newItem = {
                    id_prod: parseInt(productId),
                    cantidad: quantity,
                    descripcion_prod: productName, // Usar el nombre del producto del select
                    costo_unitario_venta: productPrice,
                    descuento_linea: parseFloat(calculatedDiscountAmount.toFixed(2)),
                    subtotal_linea_neto: parseFloat(subtotalNetoLinea.toFixed(2))
                };

                // Evitar duplicados basados solo en id_prod (podrías necesitar una lógica más compleja si permites el mismo producto con diferentes descripciones/precios)
                const existingItemIndex = reciboItems.findIndex(item => item.id_prod === newItem.id_prod);
                if (existingItemIndex > -1) {
                    alert(`"${productName}" ya está en el recibo. Si desea modificarlo, elimínelo y agréguelo de nuevo.`); return;
                } else {
                    reciboItems.push(newItem);
                    renderItemRow(newItem);
                }

                updateTotals();
                // Resetear campos
                if(productSelect) productSelect.value = '';
                if(quantityInput) quantityInput.value = 1;
                if(discountInput) discountInput.value = 0;
                if(discountTypeSelect) discountTypeSelect.value = '%'; // O tu default preferido
                updateLineSubtotal(); 
            });
        }
    }

    // Cargar ítems iniciales si se están viendo/editando
    if (initialItems && initialItems.length > 0) {
        reciboItems = []; // Limpiar para asegurar que solo se cargan los iniciales
        initialItems.forEach(item => {
            // Los detalles que vienen de 'current_recibo_detalles' en la plantilla HTML
            // usan 'descripcion_item'. El objeto JS 'newItem' usa 'descripcion_prod'.
            // Aseguramos la consistencia.
            const loadedItem = {
                id_prod: parseInt(item.id_prod),
                cantidad: parseInt(item.cantidad),
                descripcion_prod: item.descripcion_item || item.descripcion_prod || 'Producto/Servicio',
                costo_unitario_venta: parseFloat(item.costo_unitario_venta),
                descuento_linea: parseFloat(item.descuento_linea || 0),
                subtotal_linea_neto: parseFloat(item.subtotal_linea_neto)
            };
            reciboItems.push(loadedItem);
            renderItemRow(loadedItem); // renderItemRow ya considera isReadOnlyMode para el botón de eliminar
        });
    }
    
    paymentInputs.forEach(input => {
        if (input) input.addEventListener('input', updateTotals);
    });

    if (form && !isReadOnlyMode && guardarReciboBtn) { // Solo añadir listener si no es readonly
        form.addEventListener('submit', function(event) {
            event.preventDefault();
            if (reciboItems.length === 0 && !isReadOnlyMode) { // Solo alerta si estamos creando uno nuevo
                 alert("No se puede guardar un recibo vacío."); 
                 return; 
            }
            
            if(detallesJsonInput) {
                detallesJsonInput.value = JSON.stringify(reciboItems);
            } else { 
                alert("Error: Campo oculto para detalles del recibo no encontrado."); 
                return; 
            }
            
            guardarReciboBtn.disabled = true;
            guardarReciboBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Guardando...';
            
            const formData = new FormData(form);

            fetch(form.action, { 
                method: 'POST', 
                body: formData,
                headers: { 'Accept': 'application/json' }
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(errData => {
                        throw new Error(errData.message || `Error HTTP ${response.status}`);
                    }).catch(() => { throw new Error(`Error HTTP ${response.status}. Respuesta no fue JSON.`); });
                }
                return response.json(); 
            })
            .then(data => { 
                if(guardarReciboBtn){ 
                    guardarReciboBtn.disabled = false; 
                    guardarReciboBtn.innerHTML = '<i class="fas fa-save me-1"></i> Guardar Recibo'; 
                }
                if (data && data.success) {
                    if(data.message) alert(data.message); 
                    
                    // Opción de abrir PDF y redirigir (como discutimos)
                    if (data.pdf_url) {
                        window.open(data.pdf_url, '_blank');
                    }
                    if (data.view_receipt_url) { // Renombrado de redirect_url
                        setTimeout(() => { window.location.href = data.view_receipt_url; }, 500);
                    } else {
                        setTimeout(() => { window.location.reload(); }, 500);
                    }
                } else {
                    throw new Error(data.message || "Error al procesar la respuesta del servidor.");
                }
            })
            .catch(error => {
                console.error('Error en fetch o procesamiento:', error);
                alert('Error al guardar el recibo: ' + error.message);
                if(guardarReciboBtn){ 
                    guardarReciboBtn.disabled = false; 
                    guardarReciboBtn.innerHTML = '<i class="fas fa-save me-1"></i> Guardar Recibo'; 
                }
            });
        });
    }

    // Inicializar/Actualizar todo al cargar
    updateLineSubtotal();
    updateTotals();
    console.log("Formulario de Recibo Inicializado Correctamente (initializeReciboForm).");

} // Fin de initializeReciboForm

window.calcularEdad = typeof calcularEdad !== 'undefined' ? calcularEdad : undefined;
window.initializeDateDropdown = typeof initializeDateDropdown !== 'undefined' ? initializeDateDropdown : undefined;
window.initializeBodyDiagram = typeof initializeBodyDiagram !== 'undefined' ? initializeBodyDiagram : undefined;
window.initializeCostCalculator = typeof initializeCostCalculator !== 'undefined' ? initializeCostCalculator : undefined;
window.initializePatientSearch = typeof initializePatientSearch !== 'undefined' ? initializePatientSearch : undefined;
window.initializeReciboForm = initializeReciboForm; // <-- Añade la nueva función al objeto global

// --- Listener DOMContentLoaded Principal ---
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM Cargado, ejecutando inicializadores y listeners globales...");

    // Código para seleccionar texto en focus
    const inputsToSelect = document.querySelectorAll(
        'input[type="text"], input[type="number"], input[type="email"], ' +
        'input[type="tel"], input[type="search"], textarea'
    );
    inputsToSelect.forEach(input => {
        input.addEventListener('focus', function(event) {
            setTimeout(() => {
                if (typeof event.target.select === 'function') {
                    event.target.select();
                }
            }, 0);
        });
    });
    console.log(`Aplicado 'select on focus' a ${inputsToSelect.length} elementos.`);
})