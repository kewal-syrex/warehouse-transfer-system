<div class="row align-items-end mb-3">
                <div class="col-md-2">
                    <label class="form-label">Priority</label>
                    <select id="priority-filter" class="form-select form-select-sm">
                        <option value="">All Priorities</option>
                        <option value="CRITICAL">Critical</option>
                        <option value="HIGH">High</option>
                        <option value="MEDIUM">Medium</option>
                        <option value="LOW">Low</option>
                    </select>
                </div>
                <div class="col-md-2">
                    <label class="form-label">ABC Class</label>
                    <select id="abc-filter" class="form-select form-select-sm">
                        <option value="">All Classes</option>
                        <option value="A">A Items</option>
                        <option value="B">B Items</option>
                        <option value="C">C Items</option>
                    </select>
                </div>
                <div class="col-md-2">
                    <label class="form-label">Supplier</label>
                    <select id="supplier-filter" class="form-select form-select-sm"><option value="">All Suppliers</option><option value="Allied Eastern">Allied Eastern</option><option value="Chengde">Chengde</option><option value="Gpaiplus">Gpaiplus</option><option value="JINZHEN">JINZHEN</option><option value="JUN AN">JUN AN</option><option value="Jietai Filter">Jietai Filter</option><option value="King Power">King Power</option><option value="MINGZHU">MINGZHU</option><option value="Mingxing Appliance">Mingxing Appliance</option><option value="SCTF">SCTF</option><option value="SINOCONVE BELT">SINOCONVE BELT</option><option value="Special elcctronics ">Special elcctronics </option><option value="Suiking">Suiking</option><option value="Supricolor">Supricolor</option><option value="US online">US online</option><option value="Wuxi ChangSheng">Wuxi ChangSheng</option><option value="Xiangfei Metal">Xiangfei Metal</option><option value="Yangzhou Young">Yangzhou Young</option><option value="Yunda">Yunda</option><option value="ZG Blender">ZG Blender</option><option value="Zeross">Zeross</option></select>
                </div>
                <div class="col-md-2">
                    <label class="form-label">SKU Status</label>
                    <div class="dropdown">
                        <button class="btn btn-outline-secondary btn-sm form-control form-control-sm dropdown-toggle" type="button" id="status-filter-toggle" data-bs-toggle="dropdown" aria-expanded="false">
                            <span id="status-filter-text">2 Selected</span>
                        </button>
                        <ul class="dropdown-menu w-100" aria-labelledby="status-filter-toggle" id="status-filter-dropdown" style="">
                            <li>
                                <label class="dropdown-item">
                                    <input type="checkbox" id="status-select-all" class="form-check-input me-2"> Select All
                                </label>
                            </li>
                            <li><hr class="dropdown-divider"></li>
                            <li>
                                <label class="dropdown-item">
                                    <input type="checkbox" value="Active" class="form-check-input me-2 status-checkbox"> Active
                                </label>
                            </li>
                            <li>
                                <label class="dropdown-item">
                                    <input type="checkbox" value="Death Row" class="form-check-input me-2 status-checkbox"> Death Row
                                </label>
                            </li>
                            <li>
                                <label class="dropdown-item">
                                    <input type="checkbox" value="Discontinued" class="form-check-input me-2 status-checkbox"> Discontinued
                                </label>
                            </li>
                        </ul>
                    </div>
                </div>
                <div class="col-md-2">
                    <label class="form-label">Min Transfer Qty</label>
                    <input type="number" id="min-qty-filter" class="form-control form-control-sm" placeholder="0" min="0">
                </div>
                <div class="col-md-4">
                    <div class="form-check mb-2">
                        <input class="form-check-input" type="checkbox" id="show-recommendations-only">
                        <label class="form-check-label" for="show-recommendations-only">
                            Show only SKUs with recommendations
                        </label>
                    </div>
                </div>
            </div>