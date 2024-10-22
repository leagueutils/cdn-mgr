use std::collections::HashMap;
use std::io::Cursor;
use std::path::Path;

use image::{DynamicImage, GenericImageView, ImageBuffer, ImageFormat, ImageReader, Rgba, RgbaImage};
use imagetext::prelude::*;
use pyo3::prelude::*;


#[pyclass]
#[derive(Copy, Clone)]
pub struct Offset {
    x: i32,
    y: i32,
}

#[pymethods]
impl Offset {
    #[new]
    #[pyo3(signature = (x, y))]
    fn new(x: i32, y:  i32) -> Self {
        Offset{x, y}
    }

    #[getter]
    fn x(&self) -> i32 {
        self.x
    }

    #[getter]
    fn y(&self) -> i32 {
        self.y
    }
}


#[pyclass]
#[derive(Clone)]
pub struct TextAlignment {
    x: String,
    y: String,
}

#[pymethods]
impl TextAlignment {
    #[new]
    #[pyo3(signature = (x, y))]
    fn new(x: String, y:  String) -> Self {
        TextAlignment{x, y}
    }

    #[getter]
    fn x(&self) -> String {
        self.x.clone()
    }

    #[getter]
    fn y(&self) -> String {
        self.y.clone()
    }
}


#[pyclass]
#[derive(Copy, Clone)]
pub struct Size {
    pub width: i32,
    pub height: i32,
}

#[pymethods]
impl Size {
    #[new]
    #[pyo3(signature = (width, height))]
    fn new(width: i32, height:  i32) -> Self {
        Size {width, height}
    }

    #[getter]
    fn width(&self) -> i32 {
        self.width
    }

    #[getter]
    fn height(&self) -> i32 {
        self.height
    }
}


#[pyclass]
#[derive(Copy, Clone)]
pub struct Color {
    pub r: u8,
    pub g: u8,
    pub b: u8,
}

#[pymethods]
impl Color {
    #[new]
    #[pyo3(signature = (r, g, b))]
    fn new(r: u8, g: u8, b: u8) -> Self {
        Color{r: r,  g: g, b: b}
    }

    #[getter]
    fn r(&self) -> u8 {
        self.r
    }

    #[getter]
    fn g(&self) -> u8 {
        self.g
    }

    #[getter]
    fn b(&self) -> u8 {
        self.b
    }
}


#[pyclass]
#[derive(FromPyObject)]
pub struct ImageComponent {
    pub file_path: String,
    pub offset: Offset,
    pub size: Size,
}

#[pymethods]
impl ImageComponent {
    #[new]
    #[pyo3(signature = (file_path, offset, size))]
    fn new(file_path: String, offset: Offset, size: Size) -> Self {
        ImageComponent{file_path, offset, size}
    }

    #[getter]
    fn file_path(&self) -> String {
        self.file_path.clone()
    }

    #[getter]
    fn offset(&self) -> Offset {
        self.offset
    }

    #[getter]
    fn size(&self) -> Size {
        self.size
    }
}


#[pyclass]
#[derive(FromPyObject)]
pub struct TextComponent {
    pub text: String,
    pub offset: Offset,
    pub size: Size,
    pub color: Color,
    pub min_font_size: u32,
    pub max_font_size: u32,
    pub text_align: TextAlignment,
    pub wrap: String,
}

#[pymethods]
impl TextComponent {
    #[new]
    #[pyo3(signature = (text, offset, size, color, min_font_size, max_font_size, text_align, wrap))]
    fn new(text: String, offset: Offset, size: Size, color: Color, min_font_size: u32, max_font_size: u32, text_align: TextAlignment, wrap: String) -> Self {
        TextComponent{text: text, offset: offset, size: size, color: color, min_font_size: min_font_size, max_font_size: max_font_size, text_align: text_align, wrap: wrap}
    }

    #[getter]
    fn text(&self) -> String {
        self.text.clone()
    }

    #[getter]
    fn offset(&self) -> Offset {
        self.offset.clone()
    }

    #[getter]
    fn size(&self) -> Size {
        self.size.clone()
    }

    #[getter]
    fn color(&self) -> Color {
        self.color
    }

    #[getter]
    fn min_font_size(&self) -> u32 {
        self.min_font_size
    }

    #[getter]
    fn max_font_size(&self) -> u32 {
        self.max_font_size
    }

    #[getter]
    fn text_align(&self) -> TextAlignment {
        self.text_align.clone()
    }

    #[getter]
    fn wrap(&self) -> String {
        self.wrap.clone()
    }
}

//this function loads the specified fonts from a {font name: file path} dictionary
#[pyfunction]
fn load_fonts(py: Python <'_>, fonts: HashMap<String, String>) {
    py.allow_threads(|| {
        for (name, file_path) in fonts.into_iter() {
            let _ = FontDB::load_from_path(name.clone(), Path::new(&file_path)).map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                    "Failed to load font {}: {}", name, e
                ))
            });

        }
    });
}


//this function generates an image based on the specified background and fillers
#[pyfunction]
#[pyo3(signature = (background_file_path, filler_images, filler_texts, font_names))]
fn generate_image(
    py: Python <'_>,
    background_file_path: String,
    filler_images: Vec<ImageComponent>,
    filler_texts: Vec<TextComponent>,
    font_names: Vec<String>,
) -> PyResult<Vec<u8>> {
    py.allow_threads(|| -> PyResult<Vec<u8>> {
        //initialize the background image
        let mut bg = ImageReader::open(background_file_path)?.with_guessed_format()?.decode().map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Failed to load background image: {}", e))
        })?.into_rgba8();

        //rescale and paste all images onto the background
        for fi in filler_images {
            let img_patch = ImageReader::open(fi.file_path)?.with_guessed_format()?.decode().map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Failed to load filler image: {}", e))
        })?;
            let rescaled_patch = smart_rescale(&img_patch, fi.size.width.try_into().unwrap(), fi.size.height.try_into().unwrap());
            image::imageops::overlay(&mut bg, &rescaled_patch, fi.offset.x.try_into().unwrap(), fi.offset.y.try_into().unwrap());
        }

        //load fonts from database
        let font_names: Vec<&str> = font_names.iter().map(|s| &**s).collect();
        let font = FontDB::superfont(&font_names).ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "No fonts found for name(s): {:?}",
                font_names
            ))
        })?;

        //fit and paste all text components onto the background
        for ft in filler_texts {
            let (font_size, width, height) = fit_text(
                &ft.text, &font, ft.size.width, ft.size.height, ft.min_font_size, ft.max_font_size
            );
            let (text_align, x) = match &ft.text_align.x as &str {
                "l" => (TextAlign::Left, ft.offset.x),
                "m" => (TextAlign::Center, ft.offset.x + (ft.size.width - width) / 2),
                "r" => (TextAlign::Right, ft.offset.x + ft.size.width - width),
                 &_ => todo!(),
            };
            let y = match &ft.text_align.y as &str {
                "t" => ft.offset.y,
                "m" => ft.offset.y + (ft.size.height - height) / 2,
                "b" => ft.offset.y + ft.size.height - height,
                 &_ => todo!(),
            };
            let color = paint_from_rgb(ft.color.r, ft.color.g, ft.color.b);
            if &ft.wrap == "word" {
                let _ = draw_text_wrapped(
                    &mut bg,
                    &color,
                    Outline::None,
                    x as f32,
                    y as f32,
                    0.0,
                    0.0,
                    ft.size.width as f32,
                    scale(font_size as f32),
                    &font,
                    &ft.text,
                    1.0,
                    text_align,
                    WrapStyle::Word,
                );
            } else {
                let lines = ft.text.lines().map(|s| s.to_string()).collect();
                let _ = draw_text_multiline(
                    &mut bg,
                    &color,
                    Outline::None,
                    x as f32,
                    y as f32,
                    0.0,
                    0.0,
                    ft.size.width as f32,
                    scale(font_size as f32),
                    &font,
                    &lines,
                    1.0,
                    text_align,
                );
            }
        }

        let buffer = to_buffer(bg);
        return Ok(buffer)
    })
}


fn smart_rescale(
    img: &DynamicImage,
    target_width: u32,
    target_height: u32,
) -> ImageBuffer<Rgba<u8>, Vec<u8>> {
    let resized_img = img.resize(target_width, target_height, image::imageops::FilterType::Lanczos3);

    // Overlay the resized image onto the center of the output image
    let x_offset = (target_width - resized_img.width()) / 2;
    let y_offset = (target_height - resized_img.height()) / 2;
    let mut output_img = ImageBuffer::from_pixel(target_width, target_height, Rgba([0, 0, 0, 0]));
    for (x, y, pixel) in resized_img.pixels() {
        output_img.put_pixel(x + x_offset, y + y_offset, pixel);
    }

    return output_img;
}


fn to_buffer(img: RgbaImage) -> Vec<u8> {
    let mut buffer = Vec::new();
    let mut cursor = Cursor::new(&mut buffer);
    img.write_to(&mut cursor, ImageFormat::Png).unwrap();
    return buffer
}


fn fit_text(
    text: &str,
    font: &SuperFont,
    target_width: i32,
    target_height: i32,
    min_font_size: u32,
    max_font_size: u32
) -> (u32, i32, i32) {
    // early stopping if the min size doesn't fit
    let (mut w, mut h) = try_fit(text, font, min_font_size, target_width);
    if (w >= target_width) || (h >= target_height) {
        return (min_font_size, w, h);
    }

    //perform binary search on the font sizes
    let mut font_size = (min_font_size + max_font_size) / 2;
    let mut lower = min_font_size;
    let mut upper = max_font_size;
    while lower <= upper {
        //exit conditions when the search space is only one or two integers wide
        if lower == upper {
            (w, h) = try_fit(text, font, lower, target_width);
            return (lower, w, h);
        } else if lower + 1 == upper {
            (w, h) = try_fit(text, font, upper, target_width);
            if (w <= target_width) && (h <= target_height) {
                return (upper, w, h);
            }
            (w, h) = try_fit(text, font, lower, target_width);
            return (lower, w, h);
        }

        font_size = (lower + upper) / 2;
        (w, h) = try_fit(text, font, font_size, target_width);
        if (w > target_width) || (h > target_height) {
            upper = font_size - 1;
        } else if (w == target_width) || (h == target_height) {
            return (font_size,  w, h);
        } else {
            lower = font_size;
        }
    }
    return (font_size, w, h)
}


fn try_fit(text: &str, font: &SuperFont, font_size: u32, target_width: i32) -> (i32, i32) {
    let lines = text_wrap(&text, target_width.try_into().unwrap(), font, scale(font_size as f32), WrapStyle::Word, text_width);
    return text_size_multiline_with_emojis(&lines, font, scale(font_size as f32), 1.0)
}


// Expose the functions above via an importable Python extension.
#[pymodule]
fn rust_image_gen(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Offset>()?;
    m.add_class::<TextAlignment>()?;
    m.add_class::<Size>()?;
    m.add_class::<Color>()?;
    m.add_class::<ImageComponent>()?;
    m.add_class::<TextComponent>()?;

    m.add_function(wrap_pyfunction!(generate_image, m)?)?;
    m.add_function(wrap_pyfunction!(load_fonts, m)?)?;
    Ok(())
}
