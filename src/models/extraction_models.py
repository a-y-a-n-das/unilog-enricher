from pydantic import BaseModel, Field, ConfigDict

class ConflictDetails(BaseModel):

    manufacturer_part_number: str | None = None
    product_description: str | None = None

    field: str

    selected_value: str | None = None
    selected_uom: str | None = None
    selected_source: str | None = None

    conflicting_value: str | None = None
    conflicting_uom: str | None = None
    conflicting_source: str | None = None

    recommendation: str

class ExtractedField(BaseModel):
    value: str | None = None
    is_conflict: bool = False
    conflict_details: ConflictDetails | None = None



class ExtractedAttribute(BaseModel):
    label: str
    value: ExtractedField = Field(
        default_factory=ExtractedField,
    )
    uom: str | None = None




class ExtractedProduct(BaseModel):

    row_number: int


    model_config = ConfigDict(
        populate_by_name=True,
    )

    # ---------------------------------------------------------
    # Source / identity
    # ---------------------------------------------------------

    mfr_url: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="MFR URL",
    )
    ref_url_1: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Ref URL 1",
    )
    ref_url_2: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Ref URL 2",
    )
    ref_url_3: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Ref URL 3",
    )
    ref_url_4: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Ref URL 4",
    )
    ref_url_5: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Ref URL 5",
    )

    part_number: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="PART_NUMBER",
    )
    dept: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Dept",
    )
    class_: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Class",
    )
    fine: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Fine",
    )
    sku_my_part_number: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="SKU - MY_PART_NUMBER",
    )

    mfg_part_num: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Mfg_Part_Num",
    )
    part_desc: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Part_Desc",
    )
    e1_brand: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="E1_Brand",
    )
    unilog_brand: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Unilog_Brand",
    )
    dib_brand: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="DIB_Brand",
    )
    part_manuf: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Part_Manuf",
    )

    manufacturer_name: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="MANUFACTURER_NAME",
    )
    brand_name: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="BRAND_NAME",
    )
    trade_name: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="TRADE_NAME",
    )
    manufacturer_part_number: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="MANUFACTURER_PART_NUMBER",
    )
    alternate_part_number: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="ALTERNATE_PART_NUMBER",
    )

    # ---------------------------------------------------------
    # Descriptions / classification
    # ---------------------------------------------------------

    classpath: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Classpath",
    )
    mobile_desc: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="MOBILE_DESC",
    )
    invoice_desc: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="INVOICE_DESC",
    )
    short_desc: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="SHORT_DESC",
    )
    long_desc1: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="LONG_DESC1",
    )
    retail_desc: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="RETAIL_DESC",
    )
    marketing_description: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="MARKETING_DESCRIPTION",
    )

    # ---------------------------------------------------------
    # Item features 1-20
    # ---------------------------------------------------------

    item_features: list[ExtractedField] = Field(
        default_factory=list,
        max_length=20,
    )

    with_: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="With",
    )
    standard_approvals: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Standard/Approvals",
    )
    prop_65: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Prop 65",
    )
    application: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Application",
    )
    includes: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Includes",
    )
    product_name: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Product Name",
    )

    # ---------------------------------------------------------
    # Attributes 1-50
    #
    # These correspond to:
    #
    # ATTRIBUTE_LABEL 1
    # ATTRIBUTE_VALUE 1
    # ATTRIBUTE_UOM 1
    #
    # ...
    #
    # ATTRIBUTE_LABEL 50
    # ATTRIBUTE_VALUE 50
    # ATTRIBUTE_UOM 50
    #
    # ---------------------------------------------------------

    attributes: list[ExtractedAttribute] = Field(
        default_factory=list,
        max_length=50,
    )

    # ---------------------------------------------------------
    # Identifiers
    # ---------------------------------------------------------

    upc: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="UPC",
    )
    ean: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="EAN",
    )
    gtin: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="GTIN",
    )
    unspsc: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="UNSPSC",
    )

    # ---------------------------------------------------------
    # Commercial information
    # ---------------------------------------------------------

    warranty: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Warranty",
    )
    list_price: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="List Price",
    )
    selling_qty: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Selling Qty",
    )
    selling_uom: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Selling UOM",
    )
    standard_packaging_information: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Standard Packaging Information",
    )

    # ---------------------------------------------------------
    # Dimensions / weight / volume
    # ---------------------------------------------------------

    length: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="LENGTH",
    )
    length_uom: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="LENGTH_UOM",
    )
    height: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="HEIGHT",
    )
    height_uom: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="HEIGHT_UOM",
    )
    width: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="WIDTH",
    )
    width_uom: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="WIDTH_UOM",
    )
    weight: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="WEIGHT",
    )
    weight_uom: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="WEIGHT_UOM",
    )
    volume: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="VOLUME",
    )
    volume_uom: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="VOLUME_UOM",
    )

    # ---------------------------------------------------------
    # Images
    # ---------------------------------------------------------

    product_image: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Product Image",
    )
    alternate_image_1: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Alternate Image 1",
    )
    alternate_image_2: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Alternate Image 2",
    )
    alternate_image_3: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Alternate Image 3",
    )
    alternate_image_4: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Alternate Image 4",
    )

    # ---------------------------------------------------------
    # Documents / resources
    # ---------------------------------------------------------

    sds: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="SDS",
    )
    sds_1: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="SDS_1",
    )
    warranty_information: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Warranty Information",
    )
    catalog: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Catalog",
    )
    specification_sheet: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Specification Sheet",
    )
    instruction_installation_manual: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Instruction/Installation Manual",
    )
    service_manual: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Service Manual",
    )
    owners_user_manual: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Owners/User Manual",
    )
    line_drawing: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Line Drawing",
    )
    mtr: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="MTR",
    )
    rohs: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="RoHS",
    )
    full_engineering_drawing: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Full Engineering Drawing",
    )
    energy_star_guide: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Energy Star Guide",
    )
    technical_bulletin: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Technical Bulletin",
    )
    submittal: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Submittal",
    )
    compatibility_chart: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Compatibility Chart",
    )
    size_chart: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Size Chart",
    )
    product_label_insert: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Product Label/Insert",
    )
    video_link: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Video Link",
    )
    video_link_1: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Video Link 1",
    )

    # ---------------------------------------------------------
    # Final fields
    # ---------------------------------------------------------

    country_of_origin: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Country Of Origin",
    )
    discontinued: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Discontinued",
    )
    actual_image_yes_no: ExtractedField = Field(
        default_factory=ExtractedField,
        alias="Actual Image (Yes/No)",
    )


